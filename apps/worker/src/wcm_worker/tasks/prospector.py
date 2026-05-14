"""Task Celery `wcm.prospector.run_campaign`.

Construye un AgentContext con los parámetros de la campaña y delega en
ProspectorAgent. Tras crear los leads, encadena para cada uno
`wcm.fingerprinter.run` → `wcm.enricher.run` (WCM-026). El chain se lanza
asíncrono: cada lead se procesa en paralelo según slots libres del worker.

Devuelve el resumen serializable al backend de resultados Celery,
añadiendo `chained_pipelines` con el número de cadenas encoladas.
"""

from __future__ import annotations

import logging

from celery import chain

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
            created_lead_ids: list[int] = result.outputs.get("created_lead_ids", [])

        chained = _enqueue_pipeline_for_leads(created_lead_ids)
        log.info(
            "prospect_pipeline_chained",
            extra={"leads": len(created_lead_ids), "pipelines_enqueued": chained},
        )

        return {
            "status": "ok",
            "summary": result.summary,
            "outputs": result.outputs,
            "chained_pipelines": chained,
            "warnings": result.warnings,
        }
    except ProspectorError as e:
        # No reintentamos errores definitivos (API key inválida etc.).
        log.error("prospect_campaign_failed", extra={"error": str(e)})
        return {"status": "error", "error": str(e)}


def _enqueue_pipeline_for_leads(lead_ids: list[int]) -> int:
    """Encola fingerprint → enrich para cada lead. Devuelve cuántas cadenas
    se enviaron. Encolar fuera de session_scope para no retener la sesión
    mientras se hace el round-trip al broker.
    """
    sent = 0
    for lead_id in lead_ids:
        # `.si()` (signature_immutable): la salida del fingerprint NO se
        # pasa como argumento al enricher — ambos reciben solo lead_id.
        chain(
            celery_app.signature("wcm.fingerprinter.run", kwargs={"lead_id": lead_id}, immutable=True),
            celery_app.signature("wcm.enricher.run", kwargs={"lead_id": lead_id}, immutable=True),
        ).apply_async()
        sent += 1
    return sent
