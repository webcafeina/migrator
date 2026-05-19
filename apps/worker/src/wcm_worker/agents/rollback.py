"""RollbackAgent — deshace un deploy de páginas WP creadas por wp-deployer (v0.19.0).

MVP: itera `bricks_pages.wp_post_id IS NOT NULL` y hace
`DELETE /wp/v2/pages/{id}?force=true` vía REST. Resetea `wp_post_id=NULL`
para que un nuevo deploy pueda volver a crear las páginas.

NO restaura:
- Cambios a páginas existentes pre-migración (no las teníamos en snapshot).
- Configuración WPML / menús / opciones (no las migramos).
- Productos WooCommerce ni formularios Gravity Forms (los rollbacks de
  esos vendrán en v0.20.0).

Resiliencia:
- Si una página individual falla al borrarse → continúa con la siguiente,
  registra en warnings.
- Si el WP destino no responde en absoluto → fase FAILED.
- Idempotente: re-ejecutar tras un rollback parcial completa el trabajo.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RollbackAgentError
from wcm_wp_client import WpClientConfig, WpRestClient

log = logging.getLogger("wcm.worker.rollback")


class RollbackAgent(BaseAgent):
    name = "rollback"
    phase_name = "rollback"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RollbackAgentError("RollbackAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RollbackAgentError(f"Project {ctx.project_id} no encontrado")

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise RollbackAgentError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        pages = list(
            ctx.session.execute(
                select(BricksPage).where(
                    BricksPage.project_id == project.id,
                    BricksPage.wp_post_id.is_not(None),
                )
            ).scalars().all()
        )
        if not pages:
            return AgentResult(
                summary=f"Project {project.id}: 0 páginas a borrar (nada que deshacer).",
                outputs={"pages_deleted": 0, "pages_failed": 0},
            )

        deleted, failed, warnings = asyncio.run(self._rollback(wp_config, pages))
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id} rollback · {deleted} páginas borradas, "
                f"{failed} fallidas."
            ),
            outputs={
                "pages_deleted": deleted,
                "pages_failed": failed,
                "target": wp_config.site_url,
            },
            warnings=warnings,
        )

    @staticmethod
    async def _rollback(
        wp_config: WpClientConfig, pages: list[BricksPage]
    ) -> tuple[int, int, list[str]]:
        deleted = 0
        failed = 0
        warnings: list[str] = []
        async with WpRestClient(wp_config) as rest:
            for bp in pages:
                wp_post_id = bp.wp_post_id
                if wp_post_id is None:
                    continue
                try:
                    await rest.delete_page(wp_post_id, force=True)
                    bp.wp_post_id = None
                    deleted += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    msg = f"Página WP id={wp_post_id} (slug={bp.slug}) falló: {type(e).__name__}: {e}"
                    warnings.append(msg)
                    log.warning(
                        "rollback_page_failed",
                        extra={"wp_post_id": wp_post_id, "error": str(e)},
                    )
        return deleted, failed, warnings
