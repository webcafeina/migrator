"""Task Celery `wcm.prospector.run_campaign`.

Construye un AgentContext con los parámetros de la campaña y delega en
ProspectorAgent. Tras crear los leads, encadena para cada uno
`wcm.fingerprinter.run` → `wcm.enricher.run`. El chain se lanza
asíncrono: cada lead se procesa en paralelo según slots libres del worker.

Mantiene actualizada la fila `Campaign` correspondiente:
- Al empezar: status RUNNING.
- Al terminar prospect (con éxito): created_lead_ids + warnings. Si 0
  leads, también cierra con COMPLETED. Si hubo leads, deja que el
  enricher cierre (al detectar todos enriched).
- Si falla: status FAILED + error.

Devuelve el resumen serializable al backend de resultados Celery,
añadiendo `chained_pipelines` con el número de cadenas encoladas.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from wcm_db.models.campaigns import Campaign
from wcm_types.enums import CampaignStatus
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
    task_id = self.request.id
    log.info(
        "prospect_campaign_task",
        extra={"sector": sector, "region": region, "target_count": target_count, "task_id": task_id},
    )
    agent = ProspectorAgent()
    try:
        with session_scope() as session:
            # Marcar Campaign como RUNNING (si existe — puede no existir
            # si la task se encoló por CLI/script sin pasar por POST /launch).
            campaign = _find_campaign_by_task_id(session, task_id)
            if campaign is not None:
                campaign.status = CampaignStatus.RUNNING

            ctx = AgentContext(
                session=session,
                extra={
                    "sector": sector,
                    "region": region,
                    "target_count": target_count,
                    "exclude_domains": exclude_domains or [],
                    "campaign_id": campaign.id if campaign else None,
                },
            )
            result = agent.run(ctx)
            created_lead_ids: list[int] = result.outputs.get("created_lead_ids", [])

            # Actualizar Campaign con los lead_ids creados.
            if campaign is not None:
                campaign.created_lead_ids = list(created_lead_ids)
                campaign.warnings = list(result.warnings or [])
                if len(created_lead_ids) == 0:
                    # No hay leads → no habrá chain enrich → cerramos ya.
                    campaign.status = CampaignStatus.COMPLETED
                    campaign.completed_at = datetime.now(UTC)

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
        log.error("prospect_campaign_failed", extra={"error": str(e)})
        # Marcar Campaign como FAILED.
        with session_scope() as session:
            campaign = _find_campaign_by_task_id(session, task_id)
            if campaign is not None:
                campaign.status = CampaignStatus.FAILED
                campaign.error = str(e)
                campaign.completed_at = datetime.now(UTC)
        return {"status": "error", "error": str(e)}


def _find_campaign_by_task_id(session, task_id: str | None) -> Campaign | None:
    if not task_id:
        return None
    stmt = select(Campaign).where(Campaign.task_id == task_id)
    return session.execute(stmt).scalar_one_or_none()


def _enqueue_pipeline_for_leads(lead_ids: list[int]) -> int:
    """Encola fingerprint Y enrich para cada lead en paralelo. Devuelve
    cuántas parejas se enviaron.

    Antes usábamos `chain(fingerprint, enrich)` pero si fingerprint
    fallaba (URL inalcanzable, timeout, cualquier excepción del agent)
    el chain rompía y `enrich` nunca corría → el lead se quedaba en
    DISCOVERED para siempre → la Campaign nunca se cerraba.

    Encolando ambos por separado, `enrich` corre aunque fingerprint
    falle. El único efecto colateral: si enrich corre antes que
    fingerprint termine, el score baja 20 puntos (no contará el builder
    detectado). Aceptable para no atascar pipelines.
    """
    sent = 0
    for lead_id in lead_ids:
        celery_app.send_task("wcm.fingerprinter.run", kwargs={"lead_id": lead_id})
        celery_app.send_task("wcm.enricher.run", kwargs={"lead_id": lead_id})
        sent += 1
    return sent
