"""Task Celery `wcm.rollback.run_project`.

Encolada por el API (`POST /api/v1/projects/{id}/rollback`). Ejecuta
el RollbackAgent y marca el proyecto como ROLLED_BACK al terminar.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from wcm_db.models.projects import Project
from wcm_types.enums import ProjectStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.rollback import RollbackAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.integrations.events import publish_phase_event

log = logging.getLogger("wcm.worker.tasks.rollback")


@celery_app.task(name="wcm.rollback.run_project", bind=True, max_retries=0)
def run_rollback(self, project_id: int) -> dict:
    log.info("rollback_start", extra={"project_id": project_id})

    publish_phase_event(project_id, "rollback", "running")

    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            return {"project_id": project_id, "status": "not_found"}

        agent = RollbackAgent()
        ctx = AgentContext(session=session, project_id=project_id)
        try:
            result = agent.run(ctx)
        except Exception as e:  # noqa: BLE001
            log.exception("rollback_failed", extra={"project_id": project_id})
            publish_phase_event(
                project_id,
                "rollback",
                "failed",
                summary=f"{type(e).__name__}: {e}",
            )
            raise

        project.status = ProjectStatus.ROLLED_BACK
        project.completed_at = datetime.now(UTC)
        session.flush()

        publish_phase_event(
            project_id, "rollback", "completed", summary=result.summary
        )

    return {
        "project_id": project_id,
        "status": "rolled_back",
        "pages_deleted": result.outputs.get("pages_deleted", 0),
        "pages_failed": result.outputs.get("pages_failed", 0),
    }
