"""Task Celery `wcm.publish.run_project`.

Encolada por el API (`POST /api/v1/projects/{id}/publish`). Ejecuta
el PublishAgent para pasar todas las páginas migradas de draft → publish.
NO modifica project.status (es una operación ortogonal al pipeline).
"""

from __future__ import annotations

import logging

from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.publish import PublishAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.integrations.events import publish_phase_event

log = logging.getLogger("wcm.worker.tasks.publish")


@celery_app.task(name="wcm.publish.run_project", bind=True, max_retries=0)
def run_publish(self, project_id: int) -> dict:
    log.info("publish_start", extra={"project_id": project_id})

    publish_phase_event(project_id, "publish", "running")

    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            return {"project_id": project_id, "status": "not_found"}

        agent = PublishAgent()
        ctx = AgentContext(session=session, project_id=project_id)
        try:
            result = agent.run(ctx)
        except Exception as e:  # noqa: BLE001
            log.exception("publish_failed", extra={"project_id": project_id})
            publish_phase_event(
                project_id,
                "publish",
                "failed",
                summary=f"{type(e).__name__}: {e}",
            )
            raise

        session.flush()

        publish_phase_event(
            project_id, "publish", "completed", summary=result.summary
        )

    return {
        "project_id": project_id,
        "status": "published",
        "pages_published": result.outputs.get("pages_published", 0),
        "pages_failed": result.outputs.get("pages_failed", 0),
    }
