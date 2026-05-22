"""RedesignTemplatesAgent — pipeline templates Bricks (Sprint v0.25.0 B5).

Implementación real (substituye el STUB inicial). Cuando
`Project.design_method == 'templates'`:

1. Carga `Project.brief_json` (producido por BriefGeneratorAgent).
2. Por cada `Brief.pages[i]`:
   - Para cada `section in brief_page["sections"]`:
     - `SectionPicker.pick(section.type, brief.business.name,
       brief.business.sector, brief.business.tone_of_voice)`
       → elige template del catálogo `docs/templates/brickstemplate/`
       (o `brickstemplate-mock/` en tests).
     - `SlotMapper.apply(template, section, slot_map)` → árbol Bricks
       con placeholders rellenados.
   - Concatena los árboles de todas las secciones en un page content
     `[...elements de section 1..., ...elements de section 2..., ...]`.
   - UPSERT `bricks_pages` con (project_id, slug, lang) + bricks_json.

3. Si `SectionPicker.pick()` devuelve None para una sección → crea
   ResidualTask para que el operador pickee manualmente desde dashboard.

4. Idempotente: UPSERT por (project_id, slug, lang) — restart/resume
   conservan filas previas. (Patrón ya usado en BricksTranspilerAgent.)

Catálogo:
- Producción: `docs/templates/brickstemplate/` (poblado por
  `scripts/import_brickstemplate.py` + curación manual operador).
- Tests: `docs/templates/brickstemplate-mock/`.
- Override via env `WCM_TEMPLATES_CATALOG_DIR` (path absoluto).

Sin catálogo → SKIPPED + warning (operador ejecuta import + curación).

Errores tipados: `RedesignAgentError(blocks_pipeline=False)`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from wcm_bricks_transpiler.redesign import (
    SectionPicker,
    SlotMapper,
)
from wcm_db.models.assets import Asset
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import (
    ResidualCategory,
    ResidualStatus,
    ScrapeStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RedesignAgentError

log = logging.getLogger("wcm.worker.redesign_templates")


#: Path por defecto del catálogo (relativo al root del repo). En tests
#: se usa el mock; en producción el real. Override env-driven.
DEFAULT_CATALOG_PROD = Path("docs/templates/brickstemplate")
DEFAULT_CATALOG_MOCK = Path("docs/templates/brickstemplate-mock")


class RedesignTemplatesAgent(BaseAgent):
    name = "redesign-templates"
    phase_name = "redesign_templates"

    def __init__(
        self,
        *,
        catalog_dir: Path | None = None,
        section_picker: SectionPicker | None = None,
        slot_mapper: SlotMapper | None = None,
    ) -> None:
        # Resolver catalog_dir: arg > env > prod default.
        if catalog_dir is None:
            env_dir = os.environ.get("WCM_TEMPLATES_CATALOG_DIR", "").strip()
            if env_dir:
                catalog_dir = Path(env_dir)
            else:
                catalog_dir = self._resolve_default_catalog()
        self.catalog_dir = catalog_dir
        self._injected_picker = section_picker
        self._injected_mapper = slot_mapper

    @staticmethod
    def _resolve_default_catalog() -> Path:
        """Devuelve `prod` si existe, si no `mock` (para desarrollo).
        Busca relativo al cwd y absoluto."""
        for candidate in (DEFAULT_CATALOG_PROD, DEFAULT_CATALOG_MOCK):
            if candidate.exists():
                return candidate
            abs_cwd = Path.cwd() / candidate
            if abs_cwd.exists():
                return abs_cwd
        # Fallback: prod path (aunque no exista — el agente lo detectará
        # y emitirá SKIPPED con summary explicativo).
        return DEFAULT_CATALOG_PROD

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("RedesignTemplatesAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")

        # v0.26.0 — corre en modo `templates` puro Y en modo Hybrid (None).
        # En Hybrid, cubre solo las secciones con design_method=templates
        # y emite placeholders para las secciones AI (que RedesignAIAgent
        # rellenará después).
        if project.design_method not in (None, "templates"):
            return AgentResult(
                summary=(
                    f"Project {project.id}: design_method={project.design_method!r} "
                    "→ redesign_templates SKIPPED"
                ),
                outputs={"skipped": True, "reason": "design_method_mismatch"},
            )

        brief = project.brief_json
        if not brief or not brief.get("pages"):
            return AgentResult(
                summary=f"Project {project.id}: sin brief_json → SKIPPED",
                outputs={"skipped": True, "reason": "no_brief"},
                warnings=["BriefGenerator debe correr antes de RedesignTemplates"],
            )

        # Construir picker + mapper (inyectables para tests).
        picker = self._injected_picker or SectionPicker(catalog_dir=self.catalog_dir)
        if not picker.templates_index:
            return AgentResult(
                summary=(
                    f"Project {project.id}: catálogo de templates vacío "
                    f"en {self.catalog_dir} → SKIPPED"
                ),
                outputs={"skipped": True, "reason": "empty_catalog"},
                warnings=[
                    f"Ejecutar `python scripts/import_brickstemplate.py` "
                    f"para poblar {self.catalog_dir} con templates curados."
                ],
            )

        asset_resolver = self._build_asset_resolver(ctx, project.id)
        mapper = self._injected_mapper or SlotMapper(asset_resolver=asset_resolver)

        business = brief.get("business", {})
        business_name = business.get("name", project.client_name or "Cliente")
        business_sector = business.get("sector")
        business_tone = business.get("tone_of_voice")

        total_sections = 0
        templates_used = 0
        sections_unresolved = 0
        residual_count = 0
        pages_generated = 0

        for brief_page in brief["pages"]:
            page_slug = brief_page.get("slug") or "/"
            page_title = brief_page.get("title") or page_slug
            sections = brief_page.get("sections") or []
            if not sections:
                log.info(
                    "redesign_templates_empty_page",
                    extra={"project_id": project.id, "slug": page_slug},
                )
                continue

            page_content: list[dict[str, Any]] = []
            for section_index, section in enumerate(sections):
                total_sections += 1
                section_type = section.get("type")
                if not section_type:
                    continue
                # v0.26.0 — Hybrid: skip secciones AI; emite placeholder
                # vacío que RedesignAIAgent rellenará después. Mantener
                # el marker `_brief_section_index` permite identificar
                # qué chunk pertenece a qué sección del Brief.
                section_method = section.get("design_method")
                if section_method == "ai":
                    placeholder = self._build_ai_placeholder(
                        section_index=section_index,
                        section_type=section_type,
                    )
                    page_content.extend(placeholder)
                    continue
                picked = picker.pick(
                    section_type=section_type,
                    business_name=business_name,
                    business_sector=business_sector,
                    business_tone=business_tone,
                )
                if picked is None:
                    sections_unresolved += 1
                    residual_count += self._emit_residual_for_unpicked(
                        ctx, project, page_slug, section,
                    )
                    continue
                applied = mapper.apply(
                    template=picked.template_json,
                    section=section,
                    slot_map=picked.slot_map,
                )
                # `applied` shape: {"content": [...]}. Concatenamos los
                # elementos al page content. v0.26.0 — añadimos marker
                # `_brief_section_index` al root para que el merge en
                # /preview/regenerate-section funcione.
                applied_content = applied.get("content") or []
                self._tag_root_section(applied_content, section_index)
                page_content.extend(applied_content)
                templates_used += 1

            if not page_content:
                log.warning(
                    "redesign_templates_page_empty",
                    extra={"project_id": project.id, "slug": page_slug},
                )
                continue

            self._upsert_bricks_page(
                ctx, project, page_slug, page_title, page_content,
            )
            pages_generated += 1

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: redesign templates · "
                f"{pages_generated} páginas · "
                f"{templates_used}/{total_sections} secciones resueltas · "
                f"{sections_unresolved} residuales"
            ),
            outputs={
                "skipped": False,
                "pages_generated": pages_generated,
                "templates_used": templates_used,
                "sections_total": total_sections,
                "sections_unresolved": sections_unresolved,
            },
            residual_tasks_created=residual_count,
        )

    # ---------- helpers ----------

    def _build_asset_resolver(
        self, ctx: AgentContext, project_id: int
    ):
        """Devuelve un callable `asset_id → {url, wp_attachment_id, alt_text}`
        que consulta BD on-demand. SQLAlchemy identity-map cachea las
        repetidas dentro de la misma sesión."""
        def _resolver(asset_id: int) -> dict[str, Any]:
            asset = ctx.session.get(Asset, asset_id)
            if asset is None:
                return {"url": "", "wp_attachment_id": None, "alt_text": ""}
            return {
                "url": asset.wp_source_url or (
                    f"https://cdn/{asset.r2_key}" if asset.r2_key else ""
                ),
                "wp_attachment_id": asset.wp_attachment_id,
                "alt_text": asset.alt_text or "",
            }
        return _resolver

    def _upsert_bricks_page(
        self,
        ctx: AgentContext,
        project: Project,
        slug: str,
        title: str,
        content: list[dict[str, Any]],
    ) -> None:
        """UPSERT por `(project_id, slug, lang)`. Mismo patrón que
        BricksTranspilerAgent legacy para evitar UniqueViolation.
        """
        lang = project.primary_lang
        existing = ctx.session.execute(
            select(BricksPage).where(
                BricksPage.project_id == project.id,
                BricksPage.slug == slug,
                BricksPage.lang == lang,
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.title = title
            existing.bricks_json = content
            existing.status = ScrapeStatus.SUCCESS
            existing.last_import_error = None
        else:
            bp = BricksPage(
                project_id=project.id,
                page_id=None,  # rediseño no liga a scraped_page
                slug=slug,
                title=title,
                lang=lang,
                bricks_json=content,
                bricks_schema_version="2.0",
                status=ScrapeStatus.SUCCESS,
            )
            ctx.session.add(bp)

    @staticmethod
    def _tag_root_section(
        content: list[dict[str, Any]], section_index: int
    ) -> None:
        """v0.26.0 — marca el primer elemento `section` (parent='0') del
        subtree con `settings._brief_section_index = j` para que el merge
        de regenerate-section sepa identificarlo.
        """
        for el in content:
            if el.get("parent") == "0" and el.get("name") == "section":
                settings = el.setdefault("settings", {})
                settings["_brief_section_index"] = section_index
                break

    @staticmethod
    def _build_ai_placeholder(
        *, section_index: int, section_type: str
    ) -> list[dict[str, Any]]:
        """v0.26.0 — placeholder vacío para secciones con `design_method=ai`.

        Una única `section` root sin hijos, marcada con `_pending_ai: True`.
        Si RedesignAIAgent falla o no corre, el operador ve un hueco en
        el draft WP y puede regenerar manualmente desde dashboard.
        """
        # ID determinista (mismo en re-runs sin perder identidad).
        section_id = f"pai{section_index:03d}"[:6]
        return [
            {
                "id": section_id,
                "name": "section",
                "parent": "0",
                "children": [],
                "settings": {
                    "_brief_section_index": section_index,
                    "_brief_section_type": section_type,
                    "_pending_ai": True,
                    "_padding": {
                        "top": "80px",
                        "right": "20px",
                        "bottom": "80px",
                        "left": "20px",
                    },
                },
            }
        ]

    def _emit_residual_for_unpicked(
        self,
        ctx: AgentContext,
        project: Project,
        page_slug: str,
        section: dict[str, Any],
    ) -> int:
        """Cuando SectionPicker no encuentra template, crea ResidualTask
        para que el operador pickee manualmente desde dashboard."""
        section_type = section.get("type", "unknown")
        task = ResidualTask(
            project_id=project.id,
            title=(
                f"Sección sin template — página '{page_slug}' "
                f"tipo '{section_type}'"
            ),
            description=(
                f"El SectionPicker no encontró ningún template del "
                f"catálogo `{self.catalog_dir}` para sector="
                f"{project.business_sector!r}, tone={project.tone_of_voice!r}, "
                f"category={section_type!r}. "
                "Ampliar el catálogo o pickear manualmente desde el dashboard."
            ),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=15,
            screenshot_paths=[],
            status=ResidualStatus.OPEN,
            generated_by="redesign_templates",
        )
        ctx.session.add(task)
        return 1
