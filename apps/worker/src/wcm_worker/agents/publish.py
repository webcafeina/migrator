"""PublishAgent — cambia las páginas WP del proyecto a status=publish (ADR-039, v0.20.0+).

Tras wp-deployer, las páginas se crean como `draft`. El operador revisa
en QA + visual diff y, cuando da OK, dispara este agent que las publica
en lote vía WP REST.

Idempotente: si ya están publicadas (status=publish), no las toca.

Resiliencia:
- Si una página individual falla → continúa con la siguiente, registra
  en warnings.
- Si WP REST no responde → fase FAILED.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentError
from wcm_wp_client import WpClientConfig, WpRestClient

log = logging.getLogger("wcm.worker.publish")


class PublishAgentError(AgentError): ...


class PublishAgent(BaseAgent):
    name = "publish"
    phase_name = "publish"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise PublishAgentError("PublishAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise PublishAgentError(f"Project {ctx.project_id} no encontrado")

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise PublishAgentError(
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
                summary=f"Project {project.id}: 0 páginas a publicar.",
                outputs={"pages_published": 0, "pages_failed": 0},
                warnings=["bricks_pages vacío — ¿se ejecutó wp-deployer?"],
            )

        published, failed, warnings = asyncio.run(self._publish(wp_config, pages))

        return AgentResult(
            summary=(
                f"Project {project.id} publish · {published} páginas publicadas, "
                f"{failed} fallidas."
            ),
            outputs={
                "pages_published": published,
                "pages_failed": failed,
                "target": wp_config.site_url,
            },
            warnings=warnings,
        )

    @staticmethod
    async def _publish(
        wp_config: WpClientConfig, pages: list[BricksPage]
    ) -> tuple[int, int, list[str]]:
        published = 0
        failed = 0
        warnings: list[str] = []
        async with WpRestClient(wp_config) as rest:
            for bp in pages:
                try:
                    await rest.update_page(bp.wp_post_id, {"status": "publish"})
                    published += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    msg = (
                        f"Página WP id={bp.wp_post_id} (slug={bp.slug}) "
                        f"falló: {type(e).__name__}: {e}"
                    )
                    warnings.append(msg)
                    log.warning(
                        "publish_page_failed",
                        extra={"wp_post_id": bp.wp_post_id, "error": str(e)},
                    )
        return published, failed, warnings
