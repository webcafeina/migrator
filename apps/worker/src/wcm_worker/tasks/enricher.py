"""Task Celery `wcm.enricher.run`.

Encolada por el API (`POST /api/v1/leads/{id}/enrich`) y por el pipeline
de prospección (chain prospect → fingerprint → enrich, ver WCM-026).
Aplica el EnricherAgent al lead indicado.
"""

from __future__ import annotations

import logging

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

    return {
        "lead_id": lead_id,
        "summary": result.summary,
        "outputs": result.outputs,
    }
