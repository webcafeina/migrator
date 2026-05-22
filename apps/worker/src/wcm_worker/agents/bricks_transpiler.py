"""BricksTranspilerAgent — wrapper sobre wcm_bricks_transpiler.

Lee content_blocks por página, los transpila a JSON Bricks (esquema
observacional v1, ADR-014), valida y persiste en `bricks_pages`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from wcm_bricks_transpiler import (
    TranspileContext,
    transpile_page,
    validate_bricks_page,
)
from wcm_db.models.assets import Asset
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
            # v0.24.0 — resolver con BD-aware. Devuelve URL R2 si el
            # asset_uploader aún no corrió, o URL WP final si ya hay
            # `wp_source_url` poblado. Doble seguridad antes/después
            # del bloque A.
            asset_resolver=make_db_asset_resolver(ctx.session),
            # C.4 — theme sintetizado en fase anterior (puede ser None
            # si scraper httpx o ThemeStylesAgent SKIPPED).
            theme_styles=project.theme_styles_origin,
        )

        transpiled_count = 0
        validation_errors_total = 0
        residual_hints_total = 0
        # v0.23.0 — acumulador project-level de globalClasses. Cada
        # página puede emitir nuevas; al final se persisten en la option
        # `bricks_global_classes` (con dedup por id).
        all_global_classes: dict[str, dict] = {}

        for page in pages:
            stmt_blocks = (
                select(ContentBlock)
                .where(ContentBlock.page_id == page.id)
                .order_by(ContentBlock.order_index.asc())
            )
            blocks = ctx.session.execute(stmt_blocks).scalars().all()
            if not blocks:
                continue

            # transpile_page espera dicts simples (no SQLAlchemy ORM objs).
            # v0.23.0 — añadimos `element_styles` para que los mappers
            # apliquen styles del origen como Bricks settings/globalClasses.
            block_dicts = [
                {
                    "order_index": b.order_index,
                    "block_type": b.block_type,
                    "content_json": b.content_json or {},
                    "lang": b.lang,
                    "element_styles": b.element_styles,
                }
                for b in blocks
            ]

            transpile_ctx.page_id = page.id
            result = transpile_page(block_dicts, transpile_ctx)

            slug = page.slug or f"page-{page.id}"
            lang = page.lang or project.primary_lang
            # UPSERT por (project_id, slug, lang) — restart conserva
            # filas previas (ADR-041) y la unique constraint
            # `uq_bricks_pages_project_slug_lang` rompe si hacemos INSERT.
            existing = ctx.session.execute(
                select(BricksPage).where(
                    BricksPage.project_id == ctx.project_id,
                    BricksPage.slug == slug,
                    BricksPage.lang == lang,
                )
            ).scalar_one_or_none()

            validation = validate_bricks_page(result.content)
            if not validation.is_valid:
                validation_errors_total += len(validation.errors)
                new_status = ScrapeStatus.FAILED
                new_error = "; ".join(
                    f"{i.code}: {i.message}" for i in validation.errors[:5]
                )
            else:
                new_status = ScrapeStatus.SUCCESS
                new_error = None
                transpiled_count += 1

            if existing is not None:
                existing.page_id = page.id
                existing.title = page.title or "Sin título"
                existing.bricks_json = result.content
                existing.bricks_schema_version = result.schema_version
                existing.status = new_status
                existing.last_import_error = new_error
                # NO tocar wp_post_id — el rollback lo nulló y el deploy
                # de este run lo repoblará tras importar al WP.
            else:
                bricks_page = BricksPage(
                    project_id=ctx.project_id,
                    page_id=page.id,
                    slug=slug,
                    title=page.title or "Sin título",
                    lang=lang,
                    bricks_json=result.content,
                    bricks_schema_version=result.schema_version,
                    status=new_status,
                    last_import_error=new_error,
                )
                ctx.session.add(bricks_page)

            residual_hints_total += len(result.residuals)
            # v0.23.0 — acumular globalClasses (dedup por id).
            for gc in result.global_classes:
                gc_id = gc.get("id")
                if gc_id and gc_id not in all_global_classes:
                    all_global_classes[gc_id] = gc

        # Persistir globalClasses agregadas en el proyecto (campo nuevo
        # de Project si existe, o pasarlo al wp_deployer via output).
        global_classes_list = list(all_global_classes.values())
        if global_classes_list and hasattr(project, "bricks_global_classes"):
            project.bricks_global_classes = global_classes_list

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"{transpiled_count}/{len(pages)} páginas transpiladas, "
                f"{validation_errors_total} errores validación, "
                f"{residual_hints_total} hints residuales, "
                f"{len(global_classes_list)} globalClasses"
            ),
            outputs={
                "transpiled": transpiled_count,
                "validation_errors": validation_errors_total,
                "residual_hints": residual_hints_total,
                "global_classes_count": len(global_classes_list),
            },
            residual_tasks_created=residual_hints_total,
        )


def _default_asset_resolver(asset_id: int) -> dict:
    """Resolver legacy MVP — devuelve placeholder URL.

    v0.24.0 — Mantenido como compat para tests existentes. El pipeline
    productivo construye un `_db_aware_asset_resolver` con session
    inyectada (ver `make_db_asset_resolver`) que consulta `Asset.r2_key`
    o `Asset.wp_source_url` según disponibilidad.

    AssetUploaderAgent reescribe las URLs placeholder restantes tras
    el deploy. Doble seguridad: aunque transpile corra antes del
    uploader, el resolver da URL R2 si está disponible.
    """
    return {
        "url": f"/wp-content/uploads/placeholder-asset-{asset_id}.webp",
        "wp_attachment_id": None,
        "alt_text": "",
    }


def make_db_asset_resolver(session: Any) -> Callable[[int], dict]:
    """Factory: devuelve un resolver que consulta `Asset` en BD.

    Estrategia:
    1. Si `wp_source_url` poblado → URL real WP + `wp_attachment_id`.
    2. Si `r2_key` poblado pero no WP → URL R2 (fallback degradado:
       imágenes visibles sin attachment ID; el uploader posterior
       reescribirá las URLs en bricks_pages cuando se ejecute).
    3. Si nada poblado → placeholder (la `image_id` del bloque puede
       estar mal o el asset aún no se ha optimizado).
    """

    def _resolver(asset_id: int) -> dict:
        asset = session.get(Asset, asset_id)
        if asset is None:
            return _default_asset_resolver(asset_id)
        if asset.wp_source_url:
            return {
                "url": asset.wp_source_url,
                "wp_attachment_id": asset.wp_attachment_id,
                "alt_text": asset.alt_text or "",
                "width": asset.width,
                "height": asset.height,
            }
        if asset.r2_key:
            # Construir URL R2 desde public_url_base si está configurada.
            import os as _os
            base = _os.environ.get("R2_PUBLIC_URL_BASE", "").strip().rstrip("/")
            if base:
                return {
                    "url": f"{base}/{asset.r2_key.lstrip('/')}",
                    "wp_attachment_id": None,
                    "alt_text": asset.alt_text or "",
                    "width": asset.width,
                    "height": asset.height,
                }
        # Sin URL utilizable, devolver placeholder (uploader lo arregla).
        return _default_asset_resolver(asset_id)

    return _resolver
