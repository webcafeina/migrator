"""Encolar jobs Celery por nombre. Sin lógica — solo `send_task`.

Cada función refleja una operación de alto nivel que el worker
ejecutará. Los nombres deben coincidir con los `@celery_app.task(name=...)`
del worker (Fase 6). Si cambian, romper aquí también.
"""

from __future__ import annotations

from typing import Any

from wcm_api.tasks.celery_app import celery_app


def enqueue_project_pipeline(project_id: int, *, resume: bool = False) -> str:
    """Lanza el pipeline completo de migración para un proyecto.

    Devuelve el `task_id` de Celery — útil para tracking en dashboard.
    """
    result = celery_app.send_task(
        "wcm.orchestrator.run_project",
        kwargs={"project_id": project_id, "resume": resume},
    )
    return result.id


def enqueue_prospect_campaign(
    sector: str, region: str, *, target_count: int = 50, exclude_domains: list[str] | None = None
) -> str:
    result = celery_app.send_task(
        "wcm.prospector.run_campaign",
        kwargs={
            "sector": sector,
            "region": region,
            "target_count": target_count,
            "exclude_domains": exclude_domains or [],
        },
    )
    return result.id


def enqueue_lead_fingerprint(lead_id: int) -> str:
    result = celery_app.send_task(
        "wcm.fingerprinter.run", kwargs={"lead_id": lead_id}
    )
    return result.id


def enqueue_residual_sync_clickup(project_id: int) -> str:
    """Re-sincronizar tareas residuales ↔ ClickUp."""
    result = celery_app.send_task(
        "wcm.clickup.sync_residuals", kwargs={"project_id": project_id}
    )
    return result.id
