"""Task Celery `wcm.enricher.run`.

Encolada por el API (`POST /api/v1/leads/{id}/enrich`) y por el pipeline
de prospección (chain prospect → fingerprint → enrich).

Aplica el EnricherAgent al lead indicado. Tras enriquecer, si el lead
pertenece a una Campaign, comprueba si **todos** los leads de esa
campaña están ya en `ENRICHED` — si sí, cierra la Campaign
(status=COMPLETED, completed_at=now). Esto es lo que dispara que el
indicador global del dashboard deje de mostrar la campaña en curso.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select

from wcm_db.models.campaigns import Campaign
from wcm_db.models.leads import Lead
from wcm_types.enums import CampaignStatus, LeadStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.enricher import EnricherAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope

log = logging.getLogger("wcm.worker.tasks.enricher")


@celery_app.task(name="wcm.enricher.run", bind=True, max_retries=2, default_retry_delay=30)
def run(self, lead_id: int, *, skip_embedding: bool = False) -> dict:
    log.info("enricher_start", extra={"lead_id": lead_id, "skip_embedding": skip_embedding})

    with session_scope() as session:
        agent = EnricherAgent()
        result = agent.run(
            AgentContext(
                session=session,
                lead_id=lead_id,
                extra={"skip_embedding": skip_embedding},
            )
        )
        # Tras commit (al salir de session_scope), comprobamos cierre
        # de campaña en otra sesión para no mantener locks.

    _maybe_close_campaign(lead_id)

    return {
        "lead_id": lead_id,
        "summary": result.summary,
        "outputs": result.outputs,
    }


def _maybe_close_campaign(lead_id: int) -> None:
    """Si todos los leads de la campaña de `lead_id` están ENRICHED,
    cierra la Campaign (status=COMPLETED). Idempotente: si la campaña
    ya estaba completada, no hace nada.
    """
    with session_scope() as session:
        lead = session.get(Lead, lead_id)
        if lead is None or lead.campaign_id is None:
            return

        campaign = session.get(Campaign, lead.campaign_id)
        if campaign is None or campaign.status in (CampaignStatus.COMPLETED, CampaignStatus.FAILED, CampaignStatus.CANCELLED):
            return

        # ¿Quedan leads de la campaña sin enriquecer?
        pending_stmt = (
            select(func.count())
            .select_from(Lead)
            .where(Lead.campaign_id == campaign.id, Lead.status != LeadStatus.ENRICHED)
        )
        pending = session.execute(pending_stmt).scalar_one()
        if pending == 0:
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.now(UTC)
            log.info("campaign_completed", extra={
                "campaign_id": campaign.id, "task_id": campaign.task_id,
                "leads": len(campaign.created_lead_ids or []),
            })
