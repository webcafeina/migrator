"""Manejo global de errores tipados → HTTP responses uniformes.

Estrategia:
- Cada subagente/skill tiene su jerarquía de errores (`WpClientError`,
  `BricksTranspileError`, etc.). En lugar de capturarlos uno por uno en
  cada endpoint, los mapeamos centralmente a HTTP con un envelope JSON
  estable: `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- La estructura `code` es legible por máquina (snake_case); el `message`
  es para humanos (operadores del dashboard).
- En producción, `details` se censura para no exponer stack traces;
  en development se incluye el stack para facilitar debug.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

log = logging.getLogger("wcm.api.errors")


# ---------- Errores propios del API ----------

class ApiError(Exception):
    """Errores generados dentro de la API (validación de negocio, etc.)."""

    http_status: int = status.HTTP_400_BAD_REQUEST
    code: str = "api_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ApiError):
    http_status = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ForbiddenError(ApiError):
    http_status = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ConflictError(ApiError):
    http_status = status.HTTP_409_CONFLICT
    code = "conflict"


class UnauthorizedError(ApiError):
    http_status = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


# ---------- Envelope ----------

def _envelope(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


# ---------- Mapping de errores de paquetes externos ----------

def _map_wp_client_error(exc: Exception) -> tuple[int, str, dict]:
    """Mapea errores de wcm_wp_client a HTTP."""
    name = type(exc).__name__
    # Conservadores: los errores del cliente WP nunca son 200; los traducimos a 5xx
    # excepto auth/permission (4xx).
    if name == "WpAuthError":
        return 502, "wp_upstream_auth", {"upstream": str(exc)}
    if name == "WpNotFoundError":
        return 502, "wp_upstream_not_found", {"upstream": str(exc)}
    if name == "WpRateLimitError":
        return 502, "wp_upstream_rate_limit", {"upstream": str(exc)}
    if name == "WpBulkPartialError":
        return 207, "wp_bulk_partial", {"upstream": str(exc)}
    return 502, "wp_upstream_error", {"upstream": str(exc), "type": name}


def _map_bricks_error(exc: Exception) -> tuple[int, str, dict]:
    return 500, "bricks_transpile_error", {"upstream": str(exc), "type": type(exc).__name__}


# ---------- Handlers globales ----------

def register_error_handlers(app: FastAPI) -> None:
    """Registra los exception handlers en la app FastAPI."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Mapping para errores de subpaquetes (capturados por nombre para
        # evitar imports circulares).
        name = type(exc).__name__
        details: dict = {}
        if "WpClient" in name or name.startswith("Wp"):
            http_status, code, details = _map_wp_client_error(exc)
        elif "Bricks" in name:
            http_status, code, details = _map_bricks_error(exc)
        else:
            http_status = 500
            code = "internal_error"

        # Log siempre. En dev incluir stack en details.
        log.exception("unhandled_exception", extra={"path": request.url.path, "exc": name})
        from wcm_api.config import get_settings

        settings = get_settings()
        if not settings.is_production:
            details = {**details, "stack": traceback.format_exc().splitlines()[-12:]}

        return JSONResponse(
            status_code=http_status,
            content=_envelope(code, "Error interno inesperado", details),
        )


# Re-export para conveniencia
__all__ = [
    "ApiError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "UnauthorizedError",
    "register_error_handlers",
]
