"""Handler de logging para Better Stack (Logtail).

`setup_logtail_handler(token)` añade un `LogtailHandler` al root logger si
`token` está presente; sin token es no-op. La librería `logtail-python`
hace el shipping asíncrono en background (no bloquea el thread principal).
"""

from __future__ import annotations

import logging

log = logging.getLogger("wcm.api.observability.logtail")

_ATTACHED = False


def setup_logtail_handler(
    *, source_token: str | None, level: str = "info"
) -> bool:
    """Añade el handler. Devuelve True si quedó instalado.

    Idempotente: segundas llamadas no añaden handlers duplicados.
    """
    global _ATTACHED
    if _ATTACHED:
        return True
    if not source_token:
        return False
    try:
        from logtail import LogtailHandler
    except ImportError as e:  # pragma: no cover
        log.error("logtail_not_installed", extra={"error": str(e)})
        return False

    handler = LogtailHandler(source_token=source_token)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger().addHandler(handler)
    _ATTACHED = True
    log.info("logtail_handler_attached")
    return True


def reset_logtail() -> None:
    """Solo para tests."""
    global _ATTACHED
    _ATTACHED = False
