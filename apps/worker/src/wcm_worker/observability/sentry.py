"""Init de Sentry para el worker (Celery integration)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("wcm.worker.observability.sentry")

_INITIALIZED = False


def init_sentry(
    *,
    dsn: str | None,
    environment: str = "development",
    traces_sample_rate: float = 0.2,
    release: str | None = None,
) -> bool:
    global _INITIALIZED
    if _INITIALIZED:
        return True
    if not dsn:
        log.info("sentry_skipped_no_dsn", extra={"component": "worker"})
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError as e:  # pragma: no cover
        log.error("sentry_sdk_not_installed", extra={"error": str(e)})
        return False

    integrations: list[Any] = [
        CeleryIntegration(monitor_beat_tasks=True),
        SqlalchemyIntegration(),
    ]
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=integrations,
        send_default_pii=False,
        release=release,
    )
    sentry_sdk.set_tag("component", "worker")
    _INITIALIZED = True
    log.info("sentry_initialized_worker", extra={"environment": environment})
    return True


def reset_sentry() -> None:
    global _INITIALIZED
    _INITIALIZED = False
