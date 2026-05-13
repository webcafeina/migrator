"""ContentExtractorAgent — normaliza scraped_pages a content_blocks.

Decide qué extractor usar según `project.builder_source` y aplica el
extractor de wcm_scraper_core. Persiste content_blocks por página.
"""

from __future__ import annotations

from sqlalchemy import select
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_scraper_core.extractors import get_extractor
from wcm_scraper_core.extractors.wix import WixExtractor
from wcm_types.enums import BuilderType, ContentBlockSource, ScrapeStatus

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
            result = extractor.extract(page.html_clean, page.url)
            for block in result.blocks:
                cb = ContentBlock(
                    project_id=ctx.project_id,
                    page_id=page.id,
                    block_type=block.block_type,
                    order_index=block.order_index,
                    lang=block.lang or page.lang,
                    content_json=block.content_json,
                    source=ContentBlockSource.EXTRACTED,
                )
                ctx.session.add(cb)
                total_blocks += 1
                if block.block_type.value == "unknown":
                    unknown_count += 1

        ctx.session.flush()

        return AgentResult(
            summary=f"{len(pages)} páginas → {total_blocks} bloques ({unknown_count} unknown)",
            outputs={
                "pages_processed": len(pages),
                "blocks_extracted": total_blocks,
                "unknown_blocks": unknown_count,
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
