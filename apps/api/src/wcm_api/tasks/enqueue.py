"""Encolar jobs Celery por nombre. Sin lógica — solo `send_task`.

Cada función refleja una operación de alto nivel que el worker
ejecutará. Los nombres deben coincidir con los `@celery_app.task(name=...)`
del worker (Fase 6). Si cambian, romper aquí también.
"""

from __future__ import annotations

from wcm_api.tasks.celery_app import celery_app


def enqueue_project_pipeline(
    project_id: int,
    *,
    resume: bool = False,
    force_rerun_all: bool = False,
) -> str:
    """Lanza el pipeline completo de migración para un proyecto.

    Devuelve el `task_id` de Celery — útil para tracking en dashboard.

    ADR-043 — `force_rerun_all` solo aplica si `resume=True`. Si True,
    el orchestrator re-ejecuta TODAS las fases (incluso COMPLETED). Si
    False (default), Resume rápido salta las ya completed.
    """
    result = celery_app.send_task(
        "wcm.orchestrator.run_project",
        kwargs={
            "project_id": project_id,
            "resume": resume,
            "force_rerun_all": force_rerun_all,
        },
    )
    return result.id


def enqueue_prospect_campaign(
    sector: str,
    region: str,
    *,
    target_count: int = 50,
    exclude_domains: list[str] | None = None,
    task_id: str | None = None,
) -> str:
    """Encola la task del prospector. Si se pasa `task_id`, fuerza ese ID
    en Celery — útil para evitar race conditions cuando el caller necesita
    persistir una fila `campaigns` antes de que el worker pueda buscarse a
    sí mismo por task_id.
    """
    kwargs = {
        "sector": sector,
        "region": region,
        "target_count": target_count,
        "exclude_domains": exclude_domains or [],
    }
    if task_id is not None:
        result = celery_app.send_task(
            "wcm.prospector.run_campaign", kwargs=kwargs, task_id=task_id
        )
    else:
        result = celery_app.send_task("wcm.prospector.run_campaign", kwargs=kwargs)
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


def enqueue_project_rollback(project_id: int) -> str:
    """v0.19.0 — borra las páginas WP creadas por wp-deployer y marca
    el proyecto como ROLLED_BACK. Útil tras qa_failed o si el
    operador descubre un problema con el deploy."""
    result = celery_app.send_task(
        "wcm.rollback.run_project",
        kwargs={"project_id": project_id},
    )
    return result.id


def enqueue_project_publish(project_id: int) -> str:
    """v0.20.0 (ADR-039) — publica todas las páginas migradas (draft → publish).
    No modifica project.status."""
    result = celery_app.send_task(
        "wcm.publish.run_project",
        kwargs={"project_id": project_id},
    )
    return result.id
