"""Task Celery `wcm.orchestrator.run_project`.

Encolada por el API (`POST /api/v1/projects/{id}/start`). Abre sesión
DB sync, instancia Orchestrator y ejecuta el pipeline.
"""

from __future__ import annotations

import logging

from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.pipeline import Orchestrator

log = logging.getLogger("wcm.worker.tasks.orchestrator")


@celery_app.task(name="wcm.orchestrator.run_project", bind=True, max_retries=0)
def run_project(
    self,
    project_id: int,
    resume: bool = False,
    force_rerun_all: bool = False,
) -> dict:
    log.info(
        "orchestrator_start",
        extra={
            "project_id": project_id,
            "resume": resume,
            "force_rerun_all": force_rerun_all,
        },
    )

    with session_scope() as session:
        orch = Orchestrator(session, resume=resume, force_rerun_all=force_rerun_all)
        outcome = orch.run_project(project_id)

    return {
        "project_id": outcome.project_id,
        "completed_phases": outcome.completed_phases,
        "skipped_phases": outcome.skipped_phases,
        "failed_phase": outcome.failed_phase,
        "final_status": outcome.final_status.value,
    }
