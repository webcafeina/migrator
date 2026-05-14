"""BricksTranspilerAgent — wrapper sobre wcm_bricks_transpiler.

Lee content_blocks por página, los transpila a JSON Bricks (esquema
observacional v1, ADR-014), valida y persiste en `bricks_pages`.
"""

from __future__ import annotations

from sqlalchemy import select

from wcm_bricks_transpiler import (
    TranspileContext,
    transpile_page,
    validate_bricks_page,
)
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import BricksTranspilerError


class BricksTranspilerAgent(BaseAgent):
    name = "bricks-transpiler"
    phase_name = "transpile_bricks"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise BricksTranspilerError("BricksTranspilerAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise BricksTranspilerError(f"Project {ctx.project_id} no encontrado")

        # Agrupar content_blocks por scraped_page
        stmt = select(ScrapedPage).where(
            ScrapedPage.project_id == ctx.project_id,
            ScrapedPage.status == ScrapeStatus.SUCCESS,
        )
        pages = ctx.session.execute(stmt).scalars().all()

        transpile_ctx = TranspileContext(
            project_id=ctx.project_id,
            page_id=0,  # se sobreescribe por página
            page_lang=project.primary_lang,
            asset_resolver=_default_asset_resolver,
        )

        transpiled_count = 0
        validation_errors_total = 0
        residual_hints_total = 0

        for page in pages:
            stmt_blocks = (
                select(ContentBlock)
                .where(ContentBlock.page_id == page.id)
                .order_by(ContentBlock.order_index.asc())
            )
            blocks = ctx.session.execute(stmt_blocks).scalars().all()
            if not blocks:
                continue

            # transpile_page espera dicts simples (no SQLAlchemy ORM objs)
            block_dicts = [
                {
                    "order_index": b.order_index,
                    "block_type": b.block_type,
                    "content_json": b.content_json or {},
                    "lang": b.lang,
                }
                for b in blocks
            ]

            transpile_ctx.page_id = page.id
            result = transpile_page(block_dicts, transpile_ctx)

            # Validar
            validation = validate_bricks_page(result.content)
            if not validation.is_valid:
                validation_errors_total += len(validation.errors)
                # Anotar pero no aborta; la página queda con last_import_error
                bricks_page = BricksPage(
                    project_id=ctx.project_id,
                    page_id=page.id,
                    slug=page.slug or f"page-{page.id}",
                    title=page.title or "Sin título",
                    lang=page.lang or project.primary_lang,
                    bricks_json=result.content,
                    bricks_schema_version=result.schema_version,
                    status=ScrapeStatus.FAILED,
                    last_import_error="; ".join(
                        f"{i.code}: {i.message}" for i in validation.errors[:5]
                    ),
                )
            else:
                bricks_page = BricksPage(
                    project_id=ctx.project_id,
                    page_id=page.id,
                    slug=page.slug or f"page-{page.id}",
                    title=page.title or "Sin título",
                    lang=page.lang or project.primary_lang,
                    bricks_json=result.content,
                    bricks_schema_version=result.schema_version,
                    status=ScrapeStatus.SUCCESS,
                )
                transpiled_count += 1

            ctx.session.add(bricks_page)
            residual_hints_total += len(result.residuals)

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"{transpiled_count}/{len(pages)} páginas transpiladas, "
                f"{validation_errors_total} errores validación, "
                f"{residual_hints_total} hints residuales"
            ),
            outputs={
                "transpiled": transpiled_count,
                "validation_errors": validation_errors_total,
                "residual_hints": residual_hints_total,
            },
            residual_tasks_created=residual_hints_total,
        )


def _default_asset_resolver(asset_id: int) -> dict:
    """Resolver por defecto en MVP — devuelve placeholder URL.

    AssetOptimizerAgent (Fase 10) sustituirá esto por uploads reales a R2
    o WP media library. Mientras tanto el bricks_json lleva URLs
    placeholder que el wp-deployer reemplazará en commits posteriores.
    """
    return {
        "url": f"/wp-content/uploads/placeholder-asset-{asset_id}.webp",
        "wp_attachment_id": None,
        "alt_text": "",
    }
