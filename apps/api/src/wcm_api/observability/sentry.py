"""Init de Sentry para FastAPI.

Sin `SENTRY_DSN_API` configurado, `init_sentry()` no hace nada (Sentry
no se inicializa). Esto permite arrancar la API en dev sin cuenta Sentry.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("wcm.api.observability.sentry")

_INITIALIZED = False


def init_sentry(
    *,
    dsn: str | None,
    environment: str = "development",
    traces_sample_rate: float = 0.2,
    component: str = "api",
    release: str | None = None,
    extra_integrations: list[Any] | None = None,
) -> bool:
    """Inicializa el SDK de Sentry. Devuelve True si quedó inicializado.

    Idempotente: segundas llamadas con el mismo DSN son no-op.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return True
    if not dsn:
        log.info("sentry_skipped_no_dsn", extra={"component": component})
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError as e:  # pragma: no cover
        log.error("sentry_sdk_not_installed", extra={"error": str(e)})
        return False

    integrations: list[Any] = [
        StarletteIntegration(transaction_style="endpoint"),
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),
    ]
    if extra_integrations:
        integrations.extend(extra_integrations)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=integrations,
        send_default_pii=False,  # nunca enviamos PII por defecto
        release=release,
    )
    sentry_sdk.set_tag("component", component)
    _INITIALIZED = True
    log.info("sentry_initialized", extra={"component": component, "environment": environment})
    return True


def reset_sentry() -> None:
    """Solo para tests."""
    global _INITIALIZED
    _INITIALIZED = False
