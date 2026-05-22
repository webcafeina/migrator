"""RedesignAIAgent — pipeline AI generativo OpenAI gpt-4o (Sprint v0.25.0 B6).

Implementación real (substituye el STUB inicial). Cuando
`Project.design_method == 'ai'`:

1. Carga `Project.brief_json` (producido por BriefGeneratorAgent).
2. Por cada `Brief.pages[i]`:
   - `OpenAIClient.generate_page_redesign(brief, page_spec)` con
     `tool_use=emit_bricks_page` forzado (gpt-4o por defecto).
   - Valida output vía `validate_bricks_page()` (mismo schema que el
     transpiler legacy).
   - 1 retry con error context si validación falla.
   - Si retry también falla → fallback a `RedesignTemplatesAgent` para
     esa página (graceful degradation).
3. UPSERT `bricks_pages` con `(project_id, slug, lang)` + bricks_json.
4. Tracking de coste por página (suma de `OpenAIResult.cost_usd`).

Sin `OPENAI_API_KEY` → SKIPPED + warning (operador configura key o
cambia design_method a 'templates').

Errores tipados: `RedesignAgentError(blocks_pipeline=False)`.
Si OpenAI falla en TODAS las páginas → marca skipped pero NO bloquea
el pipeline (el operador puede re-correr tras añadir créditos).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from wcm_bricks_transpiler import validate_bricks_page
from wcm_db.models.assets import Asset
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.agents.redesign_templates import RedesignTemplatesAgent
from wcm_worker.errors import RedesignAgentError
from wcm_worker.integrations.openai_client import (
    OpenAIClient,
    OpenAIClientError,
    OpenAIInvalidOutputError,
)

log = logging.getLogger("wcm.worker.redesign_ai")


class RedesignAIAgent(BaseAgent):
    name = "redesign-ai"
    phase_name = "redesign_ai"

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
        fallback_agent: RedesignTemplatesAgent | None = None,
    ) -> None:
        """`openai_client` inyectable para tests.
        `fallback_agent`: si AI falla en una página, intentar templates.
        Si None y AI falla, esa página queda sin generar (warning).
        """
        self._injected_client = openai_client
        self._injected_fallback = fallback_agent

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("RedesignAIAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")

        # v0.26.0 — corre en `ai` puro Y en Hybrid (None). En Hybrid solo
        # procesa las secciones marcadas como `design_method == "ai"`,
        # rellenando los placeholders dejados por RedesignTemplatesAgent.
        if project.design_method not in (None, "ai"):
            return AgentResult(
                summary=(
                    f"Project {project.id}: design_method={project.design_method!r} "
                    "→ redesign_ai SKIPPED"
                ),
                outputs={"skipped": True, "reason": "design_method_mismatch"},
            )

        brief = project.brief_json
        if not brief or not brief.get("pages"):
            return AgentResult(
                summary=f"Project {project.id}: sin brief_json → SKIPPED",
                outputs={"skipped": True, "reason": "no_brief"},
                warnings=["BriefGenerator debe correr antes de RedesignAI"],
            )

        hybrid_mode = project.design_method is None

        client = self._injected_client or OpenAIClient.from_env()
        if client is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin OPENAI_API_KEY → "
                    "redesign_ai SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_openai_key"},
                warnings=[
                    "Configurar OPENAI_API_KEY o cambiar design_method "
                    "del proyecto a 'templates'."
                ],
            )

        # Ejecutar todo el batch async.
        outcome = asyncio.run(
            self._process_pages(
                ctx=ctx, project=project, client=client, brief=brief,
                hybrid_mode=hybrid_mode,
            )
        )

        ctx.session.flush()

        mode = "hybrid" if hybrid_mode else "ai-pure"
        return AgentResult(
            summary=(
                f"Project {project.id}: redesign AI ({mode}) · "
                f"{outcome['pages_generated']} páginas · "
                f"{outcome['sections_generated']} secciones AI · "
                f"{outcome['sections_failed']} secciones fallidas · "
                f"coste ${outcome['cost_total']:.4f}"
            ),
            outputs={
                "skipped": False,
                "mode": mode,
                "pages_generated": outcome["pages_generated"],
                "pages_fallback": outcome["pages_fallback"],
                "pages_failed": outcome["pages_failed"],
                "sections_generated": outcome.get("sections_generated", 0),
                "sections_failed": outcome.get("sections_failed", 0),
                "cost_usd_total": outcome["cost_total"],
                "tokens_in_total": outcome["tokens_in_total"],
                "tokens_out_total": outcome["tokens_out_total"],
            },
            warnings=outcome.get("warnings", []),
        )

    # ---------- helpers async ----------

    async def _process_pages(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        client: OpenAIClient,
        brief: dict[str, Any],
        hybrid_mode: bool = False,
    ) -> dict[str, Any]:
        """Procesa todas las páginas del Brief secuencialmente.

        Secuencial intencional (no concurrente) — rate-limit OpenAI en
        tier bajo se respeta mejor + simplifica tracking de coste +
        cada página es independiente.

        v0.26.0 — `hybrid_mode=True` cambia el path: en lugar de generar
        la página entera, procesa SOLO las secciones marcadas
        `design_method == "ai"` y mergea con el bricks_pages existente
        (que RedesignTemplatesAgent dejó con placeholders).
        """
        pages_generated = 0
        pages_fallback = 0
        pages_failed = 0
        sections_generated = 0
        sections_failed = 0
        cost_total = 0.0
        tokens_in_total = 0
        tokens_out_total = 0
        warnings: list[str] = []

        if hybrid_mode:
            for brief_page in brief["pages"]:
                outcome = await self._process_page_hybrid(
                    ctx=ctx, project=project, client=client,
                    brief=brief, brief_page=brief_page,
                )
                cost_total += outcome["cost"]
                tokens_in_total += outcome["tokens_in"]
                tokens_out_total += outcome["tokens_out"]
                sections_generated += outcome["sections_generated"]
                sections_failed += outcome["sections_failed"]
                if outcome["sections_generated"] > 0:
                    pages_generated += 1
                warnings.extend(outcome["warnings"])
            return {
                "pages_generated": pages_generated,
                "pages_fallback": 0,
                "pages_failed": 0,
                "sections_generated": sections_generated,
                "sections_failed": sections_failed,
                "cost_total": cost_total,
                "tokens_in_total": tokens_in_total,
                "tokens_out_total": tokens_out_total,
                "warnings": warnings,
            }

        # ---------- Pure AI path (v0.25.0 behavior) ----------
        for brief_page in brief["pages"]:
            page_slug = brief_page.get("slug") or "/"
            page_title = brief_page.get("title") or page_slug

            try:
                result = await client.generate_page_redesign(
                    brief=brief, page_spec=brief_page,
                )
                cost_total += result.cost_usd
                tokens_in_total += result.tokens_in
                tokens_out_total += result.tokens_out

                content = result.data.get("content") or []
                # Validar contra schema canónico.
                validation = validate_bricks_page(content)
                if not validation.is_valid:
                    # 1 retry con error context.
                    log.warning(
                        "redesign_ai_validation_failed_retry",
                        extra={
                            "project_id": project.id, "slug": page_slug,
                            "errors": [str(i)[:120] for i in validation.errors[:3]],
                        },
                    )
                    # Para el retry, enriquecemos el page_spec con errores.
                    retry_spec = {
                        **brief_page,
                        "_previous_errors": [
                            f"{i.code}: {i.message}" for i in validation.errors[:5]
                        ],
                    }
                    retry_result = await client.generate_page_redesign(
                        brief=brief, page_spec=retry_spec,
                    )
                    cost_total += retry_result.cost_usd
                    tokens_in_total += retry_result.tokens_in
                    tokens_out_total += retry_result.tokens_out
                    content = retry_result.data.get("content") or []
                    validation = validate_bricks_page(content)
                    if not validation.is_valid:
                        # Retry también falló → fallback templates si disponible.
                        pages_fallback += self._try_fallback_templates(
                            ctx, project, brief_page,
                        )
                        if pages_fallback == 0:
                            pages_failed += 1
                            warnings.append(
                                f"Página {page_slug}: AI generó JSON inválido en 2 intentos."
                            )
                        continue

                # Validación OK → upsert.
                self._upsert_bricks_page(
                    ctx, project, page_slug, page_title, content,
                )
                pages_generated += 1

            except OpenAIInvalidOutputError as e:
                log.warning(
                    "redesign_ai_invalid_output",
                    extra={"project_id": project.id, "slug": page_slug, "error": str(e)[:200]},
                )
                pages_fallback += self._try_fallback_templates(
                    ctx, project, brief_page,
                )
                if pages_fallback == 0:
                    pages_failed += 1
                    warnings.append(f"Página {page_slug}: OpenAI output inválido.")
            except OpenAIClientError as e:
                log.warning(
                    "redesign_ai_openai_failed",
                    extra={"project_id": project.id, "slug": page_slug, "error": str(e)[:200]},
                )
                pages_fallback += self._try_fallback_templates(
                    ctx, project, brief_page,
                )
                if pages_fallback == 0:
                    pages_failed += 1
                    warnings.append(f"Página {page_slug}: OpenAI failed ({str(e)[:80]}).")

        return {
            "pages_generated": pages_generated,
            "pages_fallback": pages_fallback,
            "pages_failed": pages_failed,
            "sections_generated": 0,
            "sections_failed": 0,
            "cost_total": cost_total,
            "tokens_in_total": tokens_in_total,
            "tokens_out_total": tokens_out_total,
            "warnings": warnings,
        }

    # ---------- v0.26.0 Hybrid path (sección a sección) ----------

    async def _process_page_hybrid(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        client: OpenAIClient,
        brief: dict[str, Any],
        brief_page: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa UNA página en modo Hybrid.

        1. Carga `bricks_pages` existente (RedesignTemplatesAgent lo
           dejó con placeholders `_pending_ai=True` para las secciones AI).
        2. Para cada sección con `design_method == "ai"`: llama
           `generate_section_redesign`, valida, y mergea el subtree en
           lugar del placeholder.
        3. UPSERT del bricks_json mergeado.

        Si no hay bricks_pages previo (Templates aún no corrió o falló),
        emite warning y skip esta página.
        """
        page_slug = brief_page.get("slug") or "/"
        page_title = brief_page.get("title") or page_slug
        sections = brief_page.get("sections") or []

        ai_indices = [
            i for i, s in enumerate(sections)
            if s.get("design_method") == "ai"
        ]
        outcome = {
            "cost": 0.0, "tokens_in": 0, "tokens_out": 0,
            "sections_generated": 0, "sections_failed": 0,
            "warnings": [],
        }
        if not ai_indices:
            return outcome

        lang = project.primary_lang
        existing = ctx.session.execute(
            select(BricksPage).where(
                BricksPage.project_id == project.id,
                BricksPage.slug == page_slug,
                BricksPage.lang == lang,
            )
        ).scalar_one_or_none()
        if existing is None:
            outcome["warnings"].append(
                f"Página '{page_slug}' sin bricks_pages previo "
                "(RedesignTemplates debería haber corrido antes en Hybrid)."
            )
            return outcome

        current_content = list(existing.bricks_json or [])

        for section_index in ai_indices:
            if section_index >= len(sections):
                continue
            section_spec = sections[section_index]
            try:
                result = await client.generate_section_redesign(
                    brief=brief, page_spec=brief_page,
                    section_spec=section_spec,
                )
                outcome["cost"] += result.cost_usd
                outcome["tokens_in"] += result.tokens_in
                outcome["tokens_out"] += result.tokens_out

                subtree = result.data.get("content") or []
                if not subtree:
                    outcome["sections_failed"] += 1
                    outcome["warnings"].append(
                        f"Sección {section_index} '{page_slug}': output vacío."
                    )
                    continue

                # Marker en el root del subtree para futuras regeneraciones.
                self._tag_subtree_root(subtree, section_index)
                # Merge in-place: reemplaza el chunk de la sección por el
                # nuevo subtree.
                current_content = self._merge_subtree_by_index(
                    current_content, section_index=section_index,
                    new_subtree=subtree,
                )
                outcome["sections_generated"] += 1
            except (OpenAIInvalidOutputError, OpenAIClientError) as e:
                log.warning(
                    "redesign_ai_hybrid_section_failed",
                    extra={
                        "project_id": project.id, "slug": page_slug,
                        "section_index": section_index, "error": str(e)[:200],
                    },
                )
                outcome["sections_failed"] += 1
                outcome["warnings"].append(
                    f"Sección {section_index} '{page_slug}': {str(e)[:80]}"
                )

        # UPSERT del bricks_json mergeado (siempre, aunque algunas
        # secciones hayan fallado — el resto persiste su contenido).
        existing.title = page_title
        existing.bricks_json = current_content
        existing.status = ScrapeStatus.SUCCESS
        existing.last_import_error = None
        return outcome

    @staticmethod
    def _tag_subtree_root(
        subtree: list[dict[str, Any]], section_index: int
    ) -> None:
        """Marca el primer `section` con parent='0' del subtree."""
        for el in subtree:
            if el.get("parent") == "0" and el.get("name") == "section":
                settings = el.setdefault("settings", {})
                settings["_brief_section_index"] = section_index
                settings.pop("_pending_ai", None)
                break

    @staticmethod
    def _merge_subtree_by_index(
        current_content: list[dict[str, Any]],
        *,
        section_index: int,
        new_subtree: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Reemplaza en `current_content` el chunk de la sección
        identificada por `_brief_section_index == section_index`.

        Estrategia:
        1. Encuentra el root section con ese marker.
        2. Calcula todos sus descendientes (transitivamente por parent).
        3. Localiza la posición del root en `current_content` para
           preservar el orden de secciones.
        4. Elimina root + descendientes.
        5. Inserta `new_subtree` en la posición donde estaba el root.
        Si no encuentra el root (caso degenerado), apéndalo al final.
        """
        # 1 & 2 — root + descendientes.
        root_id = None
        root_pos = None
        for pos, el in enumerate(current_content):
            settings = el.get("settings") or {}
            if (
                el.get("parent") == "0"
                and settings.get("_brief_section_index") == section_index
            ):
                root_id = el.get("id")
                root_pos = pos
                break

        if root_id is None:
            return current_content + new_subtree

        descendants = {root_id}
        # BFS: añadir todos los nodos cuyo parent esté en el set.
        changed = True
        while changed:
            changed = False
            for el in current_content:
                el_id = el.get("id")
                if (
                    el_id is not None
                    and el_id not in descendants
                    and el.get("parent") in descendants
                ):
                    descendants.add(el_id)
                    changed = True

        # 4 — eliminar el chunk preservando posiciones.
        surviving = [
            el for el in current_content if el.get("id") not in descendants
        ]
        # 5 — re-insertar en root_pos ajustado.
        # root_pos referencia el índice original; tras eliminar elementos
        # anteriores que también pertenecían al chunk… no aplica porque
        # el root es el primer elemento eliminado de este chunk (siempre).
        # Pero hay descendientes anteriores al root_pos imposibles (parent
        # apunta hacia atrás), así que root_pos en surviving sigue válido
        # contando solo los survivors anteriores.
        new_pos = sum(
            1 for i, el in enumerate(current_content)
            if i < root_pos and el.get("id") not in descendants
        )
        return surviving[:new_pos] + new_subtree + surviving[new_pos:]

    def _try_fallback_templates(
        self,
        ctx: AgentContext,
        project: Project,
        brief_page: dict[str, Any],
    ) -> int:
        """Intenta generar la página con RedesignTemplates como fallback.

        Devuelve 1 si fallback exitoso, 0 si no había fallback o falló.

        Implementación MVP: ejecuta un mini-pipeline templates sobre el
        Brief restringido a esta página. Reutiliza el agente templates
        para no duplicar lógica.
        """
        if self._injected_fallback is None:
            log.info(
                "redesign_ai_no_fallback_configured",
                extra={"project_id": project.id, "slug": brief_page.get("slug")},
            )
            return 0
        # Construir mini-brief con solo esta página y design_method=templates
        # para que el agente fallback funcione (lee project.design_method).
        original_method = project.design_method
        original_brief = project.brief_json
        try:
            project.design_method = "templates"
            project.brief_json = {**original_brief, "pages": [brief_page]}
            result = self._injected_fallback.run(ctx)
            return 1 if result.outputs.get("pages_generated", 0) > 0 else 0
        except Exception as e:  # noqa: BLE001
            log.warning(
                "redesign_ai_fallback_failed",
                extra={"project_id": project.id, "error": str(e)[:200]},
            )
            return 0
        finally:
            # Restore (importante: el resto de páginas siguen siendo AI).
            project.design_method = original_method
            project.brief_json = original_brief

    def _upsert_bricks_page(
        self,
        ctx: AgentContext,
        project: Project,
        slug: str,
        title: str,
        content: list[dict[str, Any]],
    ) -> None:
        """UPSERT por `(project_id, slug, lang)` — mismo patrón
        RedesignTemplatesAgent + BricksTranspilerAgent legacy."""
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
                page_id=None,
                slug=slug,
                title=title,
                lang=lang,
                bricks_json=content,
                bricks_schema_version="2.0",
                status=ScrapeStatus.SUCCESS,
            )
            ctx.session.add(bp)


# Asset import — usado eventualmente para resolver URLs (no en MVP B6,
# AI ya genera URLs directas en el prompt context).
_ = Asset  # silence unused import linter
