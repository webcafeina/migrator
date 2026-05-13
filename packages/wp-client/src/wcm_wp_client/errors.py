"""Jerarquía de errores del cliente WP.

Diseño: cada error es capturable individualmente y el orchestrator agente
decide reintentar, escalar o marcar la fase como bloqueada por humano.
"""

from __future__ import annotations


class WpClientError(Exception):
    """Raíz de la jerarquía. Captura genérica."""


# ---------- REST ----------

class WpRestError(WpClientError):
    """Error genérico de REST API."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class WpAuthError(WpRestError):
    """401/403 — credenciales mal o sin permiso. NO se reintenta."""


class WpNotFoundError(WpRestError):
    """404. NO se reintenta — el recurso no existe."""


class WpRateLimitError(WpRestError):
    """429/503 con Retry-After. Reintentar respetando Retry-After."""

    def __init__(self, message: str, *, retry_after_s: float | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after_s = retry_after_s


class WpSchemaError(WpRestError):
    """El payload recibido no matchea lo esperado (campos missing, tipo mal)."""


class WpBulkPartialError(WpClientError):
    """Bulk operation con éxitos parciales. Lleva detalle por item."""

    def __init__(
        self,
        message: str,
        *,
        successes: list[object],
        failures: list[tuple[object, Exception]],
    ) -> None:
        super().__init__(message)
        self.successes = successes
        self.failures = failures


# ---------- SSH / WP-CLI ----------

class WpSshError(WpClientError):
    """Error genérico de SSH."""


class WpSshConnectionError(WpSshError):
    """No se pudo conectar (DNS, puerto, key no autorizada)."""


class WpSshAuthError(WpSshError):
    """Key rechazada o usuario incorrecto."""


class WpCliExecutionError(WpClientError):
    """Comando WP-CLI devolvió exit_code != 0.

    Conservar stdout/stderr para diagnóstico.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        command: str = "",
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.command = command
