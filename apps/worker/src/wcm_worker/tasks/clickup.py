"""Task Celery `wcm.clickup.sync_residuals`.

Stub MVP. Implementación real en Fase 10 (integraciones externas).
"""

from __future__ import annotations

import logging

from wcm_worker.celery_app import celery_app

log = logging.getLogger("wcm.worker.tasks.clickup")


@celery_app.task(name="wcm.clickup.sync_residuals", bind=True, max_retries=0)
def sync_residuals(self, project_id: int) -> dict:
    log.warning(
        "clickup_sync_stub_called",
        extra={"project_id": project_id},
    )
    return {
        "status": "not_implemented",
        "message": (
            "ClickupSyncerAgent stubeado en Fase 6. Implementación real en Fase 10. "
            "Skill: clickup-task-creator. Team 20483773, lista Microtareas 900102088242."
        ),
        "project_id": project_id,
    }
