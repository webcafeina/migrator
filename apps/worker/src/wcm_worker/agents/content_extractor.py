"""ContentExtractorAgent — normaliza scraped_pages a content_blocks.

Decide qué extractor usar según `project.builder_source` y aplica el
extractor de wcm_scraper_core. Persiste content_blocks por página.

Adicionalmente (fix B.1 — 2026-05-20): crea filas `Asset` desde las
URLs de imagen/font/video que el extractor descubre. Sin esto la fase
`optimize_assets` no encuentra nada que descargar — el extractor
devuelve `asset_urls` pero antes nadie las persistía → 0 imágenes
migradas en el WP destino.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select

from wcm_db.models.assets import Asset
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_scraper_core.extractors import get_extractor
from wcm_scraper_core.extractors.wix import WixExtractor
from wcm_types.enums import AssetStatus, BuilderType, ContentBlockSource, ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ContentExtractorError


class ContentExtractorAgent(BaseAgent):
    name = "content-extractor"
    phase_name = "extract_content"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise ContentExtractorError("ContentExtractorAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise ContentExtractorError(f"Project {ctx.project_id} no encontrado")

        extractor = self._pick_extractor(project.builder_source)

        # B.1 — cargar hashes de assets ya persistidos para el proyecto
        # (idempotencia entre runs: si la fase se re-ejecuta no crea
        # duplicados). El UNIQUE(project_id, hash) en BD es la red
        # final, este set evita ir a BD por cada URL.
        seen_hashes: set[str] = set(
            ctx.session.execute(
                select(Asset.hash).where(Asset.project_id == ctx.project_id)
            )
            .scalars()
            .all()
        )
        assets_created = 0

        stmt = select(ScrapedPage).where(
            ScrapedPage.project_id == ctx.project_id,
            ScrapedPage.status == ScrapeStatus.SUCCESS,
        )
        pages = ctx.session.execute(stmt).scalars().all()

        total_blocks = 0
        unknown_count = 0

        for page in pages:
            if not page.html_clean:
                continue
            # v0.23.0 — pasar node_styles del Playwright fetcher al
            # extractor para que enriquezca cada ExtractedBlock con
            # element_styles via matching node_path.
            page_node_styles = page.node_styles_json or None
            if isinstance(page_node_styles, list):
                result = extractor.extract(
                    page.html_clean, page.url, node_styles=page_node_styles
                )
            else:
                # Compat: extractores que no soportan el kwarg.
                result = extractor.extract(page.html_clean, page.url)
            # AI.1 — preparar lookup section_idx → screenshot URL.
            # `scraped_pages.section_screenshots_json` viene como
            # `[{idx, selector, url}]` del scraper_origin.
            screenshots_by_idx: dict[int, str] = {}
            sections_json = page.section_screenshots_json or []
            if isinstance(sections_json, list):
                for entry in sections_json:
                    if (
                        isinstance(entry, dict)
                        and (idx := entry.get("idx")) is not None
                        and (url := entry.get("url"))
                    ):
                        screenshots_by_idx[int(idx)] = url
            for block in result.blocks:
                screenshot_url: str | None = None
                if block.section_idx is not None:
                    screenshot_url = screenshots_by_idx.get(block.section_idx)
                cb = ContentBlock(
                    project_id=ctx.project_id,
                    page_id=page.id,
                    block_type=block.block_type,
                    order_index=block.order_index,
                    lang=block.lang or page.lang,
                    content_json=block.content_json,
                    source=ContentBlockSource.EXTRACTED,
                    section_screenshot_url=screenshot_url,
                    coverage_score=block.coverage_score,
                    element_styles=block.element_styles,
                )
                ctx.session.add(cb)
                total_blocks += 1
                if block.block_type.value == "unknown":
                    unknown_count += 1

                # v0.24.0 — Bloque N. Si el bloque es NAV y trae
                # `menu_items` reales, persistirlos a nivel proyecto
                # para que wp_deployer cree el WP menu antes del
                # bricks_import_content. Solo guardamos el PRIMER NAV
                # detectado (la home suele tener el canonical).
                if (
                    block.block_type.value == "nav"
                    and isinstance(block.content_json, dict)
                    and (mi := block.content_json.get("menu_items"))
                    and project.nav_items_json is None
                ):
                    project.nav_items_json = mi
                    ctx.session.add(project)

            # B.1 — persistir URLs de assets descubiertas. Combinamos
            # imágenes + fonts + videos en un solo flujo (mismo modelo
            # `Asset`, lo distingue luego `asset_optimizer` por `mime`).
            for raw_url in (
                *result.asset_urls,
                *result.font_urls,
                *result.video_urls,
            ):
                norm = _normalize_asset_url(raw_url)
                if norm is None:
                    continue
                h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                ctx.session.add(
                    Asset(
                        project_id=ctx.project_id,
                        original_url=norm[:2048],
                        hash=h,
                        status=AssetStatus.PENDING,
                    )
                )
                assets_created += 1

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"{len(pages)} páginas → {total_blocks} bloques "
                f"({unknown_count} unknown) · {assets_created} assets nuevos"
            ),
            outputs={
                "pages_processed": len(pages),
                "blocks_extracted": total_blocks,
                "unknown_blocks": unknown_count,
                "assets_created": assets_created,
            },
            warnings=(
                [f"{unknown_count} bloques sin clasificar — generarán tareas residuales"]
                if unknown_count else []
            ),
        )

    @staticmethod
    def _pick_extractor(builder: BuilderType | None):
        if builder in {BuilderType.WIX, BuilderType.HOSTINGER_AI, BuilderType.WEBFLOW}:
            return get_extractor(builder)
        # Fallback: Wix extractor es el más genérico para HTML de webs builder
        # con `[data-mesh-id]` patterns. En producción real, si builder es
        # WordPress/Squarespace/Shopify se requeriría extractor específico.
        return WixExtractor()


def _normalize_asset_url(url: str) -> str | None:
    """Normaliza una URL de asset descubierta por el extractor.

    Acepta:
    - `https://...` y `http://...` → tal cual
    - `//cdn.com/...` (protocol-relative) → se prefija `https:`

    Descarta:
    - vacíos, `data:`, `blob:`, `javascript:`, `mailto:`, `tel:`
    - URLs relativas (`/path` o `path`) — el extractor wix.py ya filtra
      a `http*` y `//`, así que esto es defensa adicional.
    """
    url = url.strip()
    if not url:
        return None
    if url.startswith(("data:", "blob:", "javascript:", "mailto:", "tel:")):
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith(("http://", "https://")):
        return url
    return None
