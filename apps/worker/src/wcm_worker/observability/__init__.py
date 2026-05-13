"""Observabilidad del worker: structlog, Sentry (Celery integration), métricas.

Mismas convenciones que `wcm_api.observability`. Perezoso por env vars:
sin SENTRY_DSN_WORKER no inicia Sentry; sin LOGTAIL_SOURCE_TOKEN no añade
handler Logtail.
"""

from wcm_worker.observability.logging_config import configure_logging
from wcm_worker.observability.metrics import (
    AGENT_RUN_DURATION,
    AGENT_RUN_TOTAL,
    CELERY_TASK_DURATION,
    CELERY_TASK_TOTAL,
    REGISTRY,
)
from wcm_worker.observability.sentry import init_sentry

__all__ = [
    "AGENT_RUN_DURATION",
    "AGENT_RUN_TOTAL",
    "CELERY_TASK_DURATION",
    "CELERY_TASK_TOTAL",
    "REGISTRY",
    "configure_logging",
    "init_sentry",
]
