"""Configuración central de structlog + stdlib logging.

Política Webcafeína:
- **JSON renderer en prod**, **ConsoleRenderer (color) en dev**.
- Stdlib `logging` puenteado a structlog para que las libs externas
  (uvicorn, sqlalchemy, celery, httpx) emitan también JSON estructurado.
- `LOG_LEVEL` env var controla el nivel raíz (debug | info | warning | error).
- Todos los logs incluyen automáticamente `timestamp`, `level`, `logger`,
  y los `extra={}` dict-merged. Los reservados de stdlib (`msg`, `name`,
  `pathname`) no chocan porque structlog usa keyword args propios.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(
    *,
    level: str = "info",
    env: str = "development",
    extra_processors: list[Any] | None = None,
) -> None:
    """Configura structlog + stdlib. Idempotente — segundas llamadas son no-op."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if extra_processors:
        shared_processors.extend(extra_processors)

    # Para que `logging.getLogger("xxx").info(...)` también pase por structlog:
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
    # Limpiar handlers preexistentes para evitar duplicados al recargar.
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

    # Silenciar libs ruidosas a INFO independientemente del nivel raíz.
    for noisy in ("httpx", "httpcore", "asyncio", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def reset_logging() -> None:
    """Solo para tests. Restaura el estado para volver a configurar."""
    global _CONFIGURED
    _CONFIGURED = False
    structlog.reset_defaults()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
