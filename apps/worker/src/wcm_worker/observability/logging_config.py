"""Configuración de logging estructurado del worker.

Espejo de `wcm_api.observability.logging_config`. Mantenemos los módulos
separados (no `packages/observability`) para que cada proceso sea
autocontenido y desplegable sin compartir runtime.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(*, level: str = "info", env: str = "development") -> None:
    """Idempotente. Tras llamarla, `logging.getLogger(...)` produce JSON
    en prod y texto coloreable-friendly en dev (sin colores para ser
    redirigible a archivos sin escape codes).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    formatter_processors = shared_processors + [
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
    ]
    if env == "production":
        formatter_processors.append(structlog.processors.JSONRenderer())
    else:
        formatter_processors.append(structlog.dev.ConsoleRenderer(colors=False))

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=formatter_processors,
    )

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(log_level)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noisy in ("httpx", "httpcore", "asyncio", "botocore", "urllib3", "celery.beat"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def reset_logging() -> None:
    global _CONFIGURED
    _CONFIGURED = False
    structlog.reset_defaults()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
