"""Task Celery `wcm.prospector.run_campaign`.

Construye un AgentContext con los parámetros de la campaña y delega en
ProspectorAgent. Devuelve el resumen serializable al backend de
resultados Celery.
"""

from __future__ import annotations

import logging

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.prospector import ProspectorAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.errors import ProspectorError

log = logging.getLogger("wcm.worker.tasks.prospector")


@celery_app.task(name="wcm.prospector.run_campaign", bind=True, max_retries=2)
def run_campaign(
    self,
    sector: str,
    region: str,
    target_count: int = 50,
    exclude_domains: list[str] | None = None,
) -> dict:
    log.info(
        "prospect_campaign_task",
        extra={"sector": sector, "region": region, "target_count": target_count},
    )
    agent = ProspectorAgent()
    try:
        with session_scope() as session:
            ctx = AgentContext(
                session=session,
                extra={
                    "sector": sector,
                    "region": region,
                    "target_count": target_count,
                    "exclude_domains": exclude_domains or [],
                },
            )
            result = agent.run(ctx)
            return {
                "status": "ok",
                "summary": result.summary,
                "outputs": result.outputs,
                "warnings": result.warnings,
            }
    except ProspectorError as e:
        # No reintentamos errores definitivos (API key inválida etc.).
        log.error("prospect_campaign_failed", extra={"error": str(e)})
        return {"status": "error", "error": str(e)}
