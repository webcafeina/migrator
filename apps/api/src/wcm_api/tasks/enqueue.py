"""Encolar jobs Celery por nombre. Sin lógica — solo `send_task`.

Cada función refleja una operación de alto nivel que el worker
ejecutará. Los nombres deben coincidir con los `@celery_app.task(name=...)`
del worker (Fase 6). Si cambian, romper aquí también.
"""

from __future__ import annotations

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


def enqueue_lead_enrich(lead_id: int, *, skip_embedding: bool = False) -> str:
    """Encola enriquecimiento (emails, phones, socials, embedding) de un lead."""
    result = celery_app.send_task(
        "wcm.enricher.run",
        kwargs={"lead_id": lead_id, "skip_embedding": skip_embedding},
    )
    return result.id


def enqueue_outreach_send(outreach_send_id: int) -> str:
    """Encola el envío real de un OutreachSend concreto."""
    result = celery_app.send_task(
        "wcm.outreach.send_step",
        kwargs={"outreach_send_id": outreach_send_id},
    )
    return result.id


def enqueue_outreach_compose(lead_id: int, *, opt_out_token: str) -> str:
    """Encola la composición de un draft de outreach para `lead_id`.

    El `opt_out_token` lo emite la API con `issue_opt_out_token` y se pasa
    al worker para renderizar el enlace en el body sin compartir el secret.
    """
    result = celery_app.send_task(
        "wcm.outreach.compose_for_lead",
        kwargs={"lead_id": lead_id, "opt_out_token": opt_out_token},
    )
    return result.id


def enqueue_residual_sync_clickup(project_id: int) -> str:
    """Re-sincronizar tareas residuales ↔ ClickUp."""
    result = celery_app.send_task(
        "wcm.clickup.sync_residuals", kwargs={"project_id": project_id}
    )
    return result.id
