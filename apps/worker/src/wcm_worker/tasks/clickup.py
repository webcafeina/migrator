"""Task Celery `wcm.clickup.sync_residuals`.

Delega en ClickupSyncerAgent (Fase 10). Sin CLICKUP_API_TOKEN devuelve
status='skipped' sin reintentos.
"""

from __future__ import annotations

import logging

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.clickup_syncer import ClickupSyncerAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.errors import ClickupSyncerError

log = logging.getLogger("wcm.worker.tasks.clickup")


@celery_app.task(name="wcm.clickup.sync_residuals", bind=True, max_retries=2)
def sync_residuals(self, project_id: int) -> dict:
    log.info("clickup_sync_task", extra={"project_id": project_id})
    agent = ClickupSyncerAgent()
    try:
        with session_scope() as session:
            ctx = AgentContext(session=session, project_id=project_id)
            result = agent.run(ctx)
            return {
                "status": "ok" if not result.outputs.get("skipped") else "skipped",
                "summary": result.summary,
                "outputs": result.outputs,
                "warnings": result.warnings,
            }
    except ClickupSyncerError as e:
        log.error("clickup_sync_failed", extra={"error": str(e)})
        return {"status": "error", "project_id": project_id, "error": str(e)}
