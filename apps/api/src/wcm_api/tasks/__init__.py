"""Stubs de enqueue hacia Celery. Implementación real en Fase 6
(`apps/worker/`). La API solo encola; nunca ejecuta lógica de scraping
o migración inline.
"""

from wcm_api.tasks.celery_app import celery_app
from wcm_api.tasks.enqueue import (
    enqueue_lead_fingerprint,
    enqueue_project_pipeline,
    enqueue_project_rollback,
    enqueue_prospect_campaign,
    enqueue_residual_sync_clickup,
)

__all__ = [
    "celery_app",
    "enqueue_lead_fingerprint",
    "enqueue_project_pipeline",
    "enqueue_project_rollback",
    "enqueue_prospect_campaign",
    "enqueue_residual_sync_clickup",
]
