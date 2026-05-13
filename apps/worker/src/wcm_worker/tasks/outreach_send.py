"""Task Celery `wcm.outreach.send_step`.

Delega en OutreachSenderAgent. Encolada por la API tras una transición
manual READY → "enviar primer step" o por la propia secuencia
programada (Fase 11 con scheduler).
"""

from __future__ import annotations

import logging

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.outreach_sender import OutreachSenderAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.errors import OutreachSenderError

log = logging.getLogger("wcm.worker.tasks.outreach_send")


@celery_app.task(name="wcm.outreach.send_step", bind=True, max_retries=2)
def send_step(self, outreach_send_id: int) -> dict:
    log.info("outreach_send_task", extra={"outreach_send_id": outreach_send_id})
    try:
        with session_scope() as session:
            ctx = AgentContext(
                session=session,
                extra={"outreach_send_id": outreach_send_id},
            )
            result = OutreachSenderAgent().run(ctx)
            return {
                "status": "ok" if not result.outputs.get("skipped") else "skipped",
                "summary": result.summary,
                "outputs": result.outputs,
            }
    except OutreachSenderError as e:
        log.error("outreach_send_failed", extra={"error": str(e)})
        return {
            "status": "error",
            "outreach_send_id": outreach_send_id,
            "error": str(e),
        }
