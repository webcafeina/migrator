"""Task Celery `wcm.outreach.compose_for_lead`.

Delega en OutreachComposerAgent. Devuelve el sequence_id creado o un
error si la composición falló (lead sin email, opted-out previo, etc.).
"""

from __future__ import annotations

import logging

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.outreach_composer import OutreachComposerAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.errors import OutreachComposerError

log = logging.getLogger("wcm.worker.tasks.outreach")


@celery_app.task(name="wcm.outreach.compose_for_lead", bind=True, max_retries=0)
def compose_for_lead(self, lead_id: int, opt_out_token: str) -> dict:
    agent = OutreachComposerAgent()
    try:
        with session_scope() as session:
            ctx = AgentContext(
                session=session,
                lead_id=lead_id,
                extra={"opt_out_token": opt_out_token},
            )
            result = agent.run(ctx)
            return {
                "status": "ok",
                "summary": result.summary,
                "outputs": result.outputs,
            }
    except OutreachComposerError as e:
        log.warning(
            "outreach_compose_failed",
            extra={"lead_id": lead_id, "error": str(e)},
        )
        return {"status": "error", "lead_id": lead_id, "error": str(e)}
