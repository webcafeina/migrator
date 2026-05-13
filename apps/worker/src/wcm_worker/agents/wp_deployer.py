"""WpDeployerAgent — provisiona páginas Bricks en el WP destino.

MVP: asume que el WP destino ya tiene Bricks Builder activo (no
instalamos plugins automáticamente en esta fase; eso es responsabilidad
de Fase 10/12 con WPCLI).

Para cada `bricks_pages` exitosa, hace upsert de la página WP via REST y
escribe el `_bricks_page_content_2` post meta via WP-CLI (más fiable
para JSONs grandes).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_types.enums import ScrapeStatus
from wcm_wp_client import (
    WpClientConfig,
    WpCliSshClient,
    WpRestClient,
)

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import WpDeployerError


class WpDeployerAgent(BaseAgent):
    name = "wp-deployer"
    phase_name = "deploy_wp"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise WpDeployerError("WpDeployerAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise WpDeployerError(f"Project {ctx.project_id} no encontrado")

        # Para MVP, la config WP destino viene del entorno global (sandbox
        # Local). En producción, project.hosting_target_json llevará los
        # parámetros específicos del cliente.
        try:
            wp_config = WpClientConfig.from_env()
        except ValueError as e:
            raise WpDeployerError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        stmt = select(BricksPage).where(
            BricksPage.project_id == ctx.project_id,
            BricksPage.status == ScrapeStatus.SUCCESS,
        )
        bricks_pages = ctx.session.execute(stmt).scalars().all()

        if not bricks_pages:
            return AgentResult(summary="No hay bricks_pages listas para desplegar")

        # Ejecutar el async loop dentro de la task sync Celery.
        deployed, failed = asyncio.run(
            self._deploy_all(wp_config, bricks_pages, ctx)
        )

        return AgentResult(
            summary=f"{deployed} páginas desplegadas, {failed} fallidas",
            outputs={
                "deployed": deployed,
                "failed": failed,
                "target": wp_config.site_url,
            },
        )

    async def _deploy_all(
        self,
        wp_config: WpClientConfig,
        bricks_pages: list[BricksPage],
        ctx: AgentContext,
    ) -> tuple[int, int]:
        deployed = 0
        failed = 0

        async with WpRestClient(wp_config) as rest, WpCliSshClient(wp_config) as cli:
            for bp in bricks_pages:
                try:
                    # 1. Upsert de la página WP (idempotente por slug)
                    page_payload = {
                        "slug": bp.slug,
                        "title": bp.title,
                        "status": "draft",  # publicar manualmente desde dashboard
                        "content": "",  # Bricks usa post meta, no post_content
                    }
                    wp_page = await rest.upsert_page_by_slug(page_payload)
                    wp_post_id = wp_page["id"]

                    # 2. Escribir el bricks_json en post_meta via WP-CLI
                    #    (REST puede fallar con payloads grandes)
                    await cli.bricks_import_content(wp_post_id, bp.bricks_json)

                    bp.wp_post_id = wp_post_id
                    bp.last_import_error = None
                    deployed += 1
                except Exception as e:  # noqa: BLE001
                    bp.last_import_error = f"{type(e).__name__}: {e}"[:1000]
                    failed += 1

        ctx.session.flush()
        return deployed, failed
