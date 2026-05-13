"""Task Celery `wcm.fingerprinter.run`.

Encolada por el API (`POST /api/v1/leads/{id}/refingerprint`). Aplica el
FingerprinterAgent al lead indicado.
"""

from __future__ import annotations

import logging

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.fingerprinter import FingerprinterAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope

log = logging.getLogger("wcm.worker.tasks.fingerprinter")


@celery_app.task(name="wcm.fingerprinter.run", bind=True, max_retries=2, default_retry_delay=30)
def run(self, lead_id: int) -> dict:
    log.info("fingerprinter_start", extra={"lead_id": lead_id})

    with session_scope() as session:
        agent = FingerprinterAgent()
        result = agent.run(AgentContext(session=session, lead_id=lead_id))

    return {
        "lead_id": lead_id,
        "summary": result.summary,
        "outputs": result.outputs,
    }
