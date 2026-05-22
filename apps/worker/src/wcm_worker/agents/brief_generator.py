"""BriefGeneratorAgent — produce el Brief JSON canónico (Sprint v0.25.0 B2).

Fase nueva del pipeline. Posición: **entre `extract_content` y `theme_styles`**
(theme_styles pasa a ser informativo, ya no es input crítico del transpile
porque el output del rediseño lo construyen los nuevos agentes
RedesignTemplatesAgent o RedesignAIAgent a partir de este Brief).

Flujo:
1. Carga Project + ScrapedPages + ContentBlocks + Assets del proyecto.
2. Si business_description/sector/tone/target/usps están vacíos en
   Project → invoca OpenAIClient.generate_brief_metadata() con un
   resumen del scraping (gpt-4o-mini, ~$0.01/proyecto).
3. Construye el Brief JSON con shape canónica:
   {
     business: {name, description, sector, tone_of_voice, target_audience, usps},
     brand: {colors, fonts, logo_asset_id},
     navigation: [...],  # de Project.nav_items_json
     footer: {columns: [...], copyright},
     pages: [
       {slug, title, intent, sections: [{type, ...content}]}
     ]
   }
4. Persiste en Project.brief_json para alimentar pipelines siguientes.

Sin OPENAI_API_KEY → si los campos business están seteados por el
operador en wizard, sigue. Si no → marca BLOCKED_HUMAN_INPUT (el
operador debe rellenarlos manualmente).

Errores tipados: `BriefGeneratorError(blocks_pipeline=False)` —
si OpenAI falla pero los campos están seteados, sigue con esos.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from wcm_db.models.assets import Asset
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import BriefGeneratorError
from wcm_worker.integrations.openai_client import (
    OpenAIClient,
    OpenAIClientError,
)

log = logging.getLogger("wcm.worker.brief_generator")


#: Si el operador no ha rellenado estos campos en el wizard, se intenta
#: auto-detectar con OpenAI. Si OpenAI no está disponible y faltan, el
#: agente marca BLOCKED_HUMAN_INPUT y el operador rellena en dashboard.
REQUIRED_BUSINESS_FIELDS = (
    "business_description",
    "business_sector",
    "tone_of_voice",
    "target_audience",
)


class BriefGeneratorAgent(BaseAgent):
    name = "brief-generator"
    phase_name = "brief_generator"

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
    ) -> None:
        self._injected_client = openai_client

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise BriefGeneratorError("BriefGeneratorAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise BriefGeneratorError(f"Project {ctx.project_id} no existe")

        # 1) Cargar páginas + bloques.
        pages = self._load_pages(ctx, project.id)
        if not pages:
            return AgentResult(
                summary=f"Project {project.id}: sin scraped_pages, brief SKIPPED",
                outputs={"skipped": True, "reason": "no_scraped_pages"},
            )

        blocks_by_page = self._load_blocks_grouped(ctx, project.id)
        assets_by_id = self._load_assets(ctx, project.id)

        # 2) Si faltan campos business → intentar auto-detect con OpenAI.
        client = self._injected_client or OpenAIClient.from_env()
        if not self._business_fields_set(project):
            if client is None:
                # Sin OpenAI: no podemos auto-detectar. Marcar
                # BLOCKED_HUMAN_INPUT vía warning. El operador edita
                # en wizard y vuelve a lanzar.
                log.warning(
                    "brief_generator_missing_business_no_openai",
                    extra={"project_id": project.id},
                )
                return AgentResult(
                    summary=(
                        f"Project {project.id}: campos business vacíos + "
                        "sin OPENAI_API_KEY → BLOCKED. Rellenar manualmente."
                    ),
                    outputs={
                        "skipped": True,
                        "reason": "missing_business_no_openai",
                    },
                    warnings=[
                        "Faltan business_description/sector/tone/target. "
                        "Configurar OPENAI_API_KEY o editar Project desde dashboard."
                    ],
                )
            # Auto-detect.
            try:
                metadata_result = asyncio.run(
                    self._autodetect_metadata(
                        client=client, project=project, pages=pages,
                        blocks_by_page=blocks_by_page,
                    )
                )
                self._apply_metadata_to_project(project, metadata_result.data)
                ctx.session.add(project)
                log.info(
                    "brief_generator_metadata_autodetected",
                    extra={
                        "project_id": project.id,
                        "sector": metadata_result.data.get("business_sector"),
                        "tone": metadata_result.data.get("tone_of_voice"),
                        "cost_usd": metadata_result.cost_usd,
                    },
                )
            except OpenAIClientError as e:
                log.warning(
                    "brief_generator_openai_failed",
                    extra={"project_id": project.id, "error": str(e)[:200]},
                )
                # Si tenemos AL MENOS description, seguimos con lo que hay.
                if not project.business_description:
                    return AgentResult(
                        summary=(
                            f"Project {project.id}: OpenAI metadata falló + "
                            "sin business_description. BLOCKED."
                        ),
                        outputs={"skipped": True, "reason": "openai_failed_no_fallback"},
                        warnings=[str(e)[:300]],
                    )

        # 3) Construir Brief JSON canónico.
        brief = self._build_brief(
            project=project,
            pages=pages,
            blocks_by_page=blocks_by_page,
            assets_by_id=assets_by_id,
        )
        project.brief_json = brief
        ctx.session.add(project)
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: Brief generado · "
                f"{len(brief['pages'])} páginas · "
                f"sector={brief['business']['sector']} · "
                f"tone={brief['business']['tone_of_voice']}"
            ),
            outputs={
                "skipped": False,
                "n_pages": len(brief["pages"]),
                "sector": brief["business"]["sector"],
                "tone": brief["business"]["tone_of_voice"],
                "n_sections_total": sum(len(p["sections"]) for p in brief["pages"]),
                "n_nav_items": len(brief.get("navigation") or []),
            },
        )

    # ---------- helpers privados ----------

    def _load_pages(self, ctx: AgentContext, project_id: int) -> list[ScrapedPage]:
        stmt = (
            select(ScrapedPage)
            .where(
                ScrapedPage.project_id == project_id,
                ScrapedPage.status == ScrapeStatus.SUCCESS,
            )
            .order_by(ScrapedPage.depth.asc(), ScrapedPage.id.asc())
        )
        return list(ctx.session.execute(stmt).scalars())

    def _load_blocks_grouped(
        self, ctx: AgentContext, project_id: int
    ) -> dict[int, list[ContentBlock]]:
        stmt = (
            select(ContentBlock)
            .where(ContentBlock.project_id == project_id)
            .order_by(ContentBlock.page_id, ContentBlock.order_index)
        )
        out: dict[int, list[ContentBlock]] = {}
        for cb in ctx.session.execute(stmt).scalars():
            out.setdefault(cb.page_id, []).append(cb)
        return out

    def _load_assets(self, ctx: AgentContext, project_id: int) -> dict[int, Asset]:
        stmt = select(Asset).where(Asset.project_id == project_id)
        return {a.id: a for a in ctx.session.execute(stmt).scalars()}

    def _business_fields_set(self, project: Project) -> bool:
        """True si todos los campos REQUIRED_BUSINESS_FIELDS están
        seteados en el Project. usps_json es opcional (default [])."""
        return all(
            getattr(project, field, None) for field in REQUIRED_BUSINESS_FIELDS
        )

    def _apply_metadata_to_project(self, project: Project, data: dict[str, Any]) -> None:
        """Aplica solo los campos que NO estén ya seteados (operador wins)."""
        if not project.business_description:
            project.business_description = data.get("business_description")
        if not project.business_sector:
            project.business_sector = data.get("business_sector")
        if not project.tone_of_voice:
            project.tone_of_voice = data.get("tone_of_voice")
        if not project.target_audience:
            project.target_audience = data.get("target_audience")
        if not project.usps_json:
            project.usps_json = data.get("usps")

    async def _autodetect_metadata(
        self,
        *,
        client: OpenAIClient,
        project: Project,
        pages: list[ScrapedPage],
        blocks_by_page: dict[int, list[ContentBlock]],
    ) -> Any:
        """Construye scraping_summary compacto y llama OpenAI."""
        summary_parts: list[str] = []
        if project.client_name:
            summary_parts.append(f"# Cliente: {project.client_name}")
        if project.source_url:
            summary_parts.append(f"# URL origen: {project.source_url}")

        for page in pages[:5]:  # cap a 5 páginas más relevantes (home + 4 internas)
            summary_parts.append(f"\n## Página: {page.slug or '/'} — {page.title or 'Sin título'}")
            blocks = blocks_by_page.get(page.id, [])
            for b in blocks[:30]:  # cap a 30 bloques/página
                text = self._text_from_block(b)
                if text:
                    summary_parts.append(f"  - [{b.block_type.value}] {text[:200]}")
        summary = "\n".join(summary_parts)
        return await client.generate_brief_metadata(
            scraping_summary=summary,
            theme_hints=project.theme_styles_origin or {},
            fingerprint={
                "builder": project.builder_source,
                "url": project.source_url,
            },
        )

    @staticmethod
    def _text_from_block(block: ContentBlock) -> str:
        """Extrae representación textual breve de un ContentBlock."""
        cj = block.content_json or {}
        for key in ("text", "headline", "title", "html"):
            v = cj.get(key)
            if isinstance(v, str) and v.strip():
                # Strip HTML tags básico.
                import re
                return re.sub(r"<[^>]+>", " ", v).strip()
        return ""

    def _build_brief(
        self,
        *,
        project: Project,
        pages: list[ScrapedPage],
        blocks_by_page: dict[int, list[ContentBlock]],
        assets_by_id: dict[int, Asset],
    ) -> dict[str, Any]:
        """Construye el Brief JSON canónico."""
        # business
        business = {
            "name": project.client_name or (project.source_url or "Cliente"),
            "description": project.business_description or "",
            "sector": project.business_sector or "other",
            "tone_of_voice": project.tone_of_voice or "friendly",
            "target_audience": project.target_audience or "",
            "usps": list(project.usps_json or []),
        }

        # brand: extraer de theme_styles_origin
        theme = project.theme_styles_origin or {}
        brand = {
            "colors": theme.get("colors") or {},
            "fonts": theme.get("typography") or theme.get("fonts") or {},
            "google_fonts": theme.get("google_fonts") or [],
            "gradients": theme.get("gradients") or [],
            "logo_asset_id": self._find_logo_asset_id(assets_by_id),
        }

        # navigation
        navigation = list(project.nav_items_json or [])

        # footer (placeholder en MVP — el extractor v0.24.0 lo guarda en
        # content_blocks tipo FOOTER, podemos extraer copyright + columns
        # de allí pero v0.25.0 lo deja como TODO simple).
        footer = {
            "columns": [],
            "copyright": f"© {project.client_name or 'Empresa'}",
        }

        # pages: convertir cada ScrapedPage + ContentBlocks → Brief.pages
        brief_pages: list[dict[str, Any]] = []
        for page in pages:
            blocks = blocks_by_page.get(page.id, [])
            brief_page = {
                "slug": page.slug or "/",
                "title": page.title or page.slug or "Página",
                "intent": self._infer_page_intent(page, blocks),
                "sections": self._blocks_to_sections(blocks),
            }
            brief_pages.append(brief_page)

        return {
            "business": business,
            "brand": brand,
            "navigation": navigation,
            "footer": footer,
            "pages": brief_pages,
        }

    @staticmethod
    def _find_logo_asset_id(assets_by_id: dict[int, Asset]) -> int | None:
        """Heurística: primer asset cuyo alt_text contenga 'logo' o cuyo
        nombre de archivo lo contenga. None si no se detecta."""
        for asset in assets_by_id.values():
            alt = (asset.alt_text or "").lower()
            url = (asset.original_url or "").lower()
            if "logo" in alt or "logo" in url:
                return asset.id
        return None

    @staticmethod
    def _infer_page_intent(page: ScrapedPage, blocks: list[ContentBlock]) -> str:
        """Heurística: home/services/contact/about/blog/legal/other."""
        slug = (page.slug or "").lower()
        if slug in ("", "/", "home", "index", "inicio"):
            return "landing"
        if any(s in slug for s in ("contact", "contacto")):
            return "contact"
        if any(s in slug for s in ("about", "sobre", "quien", "quiénes", "nosotros")):
            return "about"
        if any(s in slug for s in ("service", "servicio", "product", "producto")):
            return "services"
        if any(s in slug for s in ("blog", "noticia", "news", "post")):
            return "blog"
        if any(s in slug for s in ("legal", "privacy", "privacidad", "cookie", "aviso", "terms")):
            return "legal"
        return "other"

    def _blocks_to_sections(
        self, blocks: list[ContentBlock]
    ) -> list[dict[str, Any]]:
        """Convierte ContentBlocks → Brief.sections agrupados.

        Brief.section shape (depende del type):
        - hero: {type, headline, subheadline, cta, image_asset_id}
        - heading: {type, text, level}
        - text: {type, html}
        - image: {type, asset_id, alt}
        - cta: {type, text, url}
        - gallery: {type, image_urls, layout}
        - grid: {type, items}
        - testimonial: {type, items}
        - pricing: {type, tiers}
        - faq: {type, items}
        - form: {type, fields}
        - slider: {type, slides}
        - tabs: {type, tabs}
        - accordion: {type, panels}
        - nav: skip (va en navigation top-level)
        - footer: skip (va en footer top-level)
        """
        sections: list[dict[str, Any]] = []
        for b in blocks:
            bt = b.block_type.value
            cj = b.content_json or {}
            if bt in ("nav", "footer", "unknown"):
                continue
            section: dict[str, Any] = {"type": bt}
            # Copia keys útiles del content_json al section.
            for key in (
                "headline", "subheadline", "text", "html", "level",
                "image_url", "asset_id", "alt", "src", "image_urls",
                "items", "tiers", "fields", "slides", "tabs", "panels",
                "cta_text", "cta_url", "bg_image_url", "composition_items",
                "menu_items", "columns",
            ):
                if key in cj:
                    section[key] = cj[key]
            sections.append(section)
        return sections
