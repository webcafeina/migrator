"""Cliente HTTP del CLI.

Wrapper sobre httpx que:
- Inyecta `Authorization: Bearer <token>` automáticamente.
- Mapea el envelope JSON de error del API (`{"error": {"code", "message"}}`)
  a `CliApiError` / `CliAuthError` con mensaje humano.
- Soporta timeout configurable.
- Logging de requests en modo `--verbose` (Fase 11 lo amplía con structlog).
"""

from __future__ import annotations

from typing import Any

import httpx

from wcm_cli.config import CliConfig, load_token
from wcm_cli.errors import CliApiError, CliAuthError, CliConfigError


class ApiClient:
    def __init__(
        self,
        config: CliConfig | None = None,
        *,
        token: str | None = None,
        require_auth: bool = True,
    ) -> None:
        self.config = config or CliConfig.load()
        # Token explícito > token cacheado > None
        self.token = token if token is not None else load_token()
        if require_auth and not self.token:
            raise CliAuthError(
                "No has iniciado sesión todavía.",
                hint="Ejecuta `wcm login` para autenticarte, o exporta WCM_TOKEN.",
            )

    @property
    def headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "wcm-cli/0.1"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ---------- low-level ----------

    def _request(
        self, method: str, path: str, *, params: dict | None = None,
        json: Any = None, expect_status: tuple[int, ...] = (200, 201, 202, 204),
    ) -> dict | list | None:
        url = f"{self.config.api_url}{path}"
        try:
            with httpx.Client(
                timeout=self.config.timeout_s, verify=self.config.verify_ssl
            ) as client:
                response = client.request(
                    method, url, params=params, json=json, headers=self.headers
                )
        except httpx.ConnectError as e:
            raise CliConfigError(
                f"No se pudo conectar al API ({self.config.api_url}).",
                hint=(
                    "Comprueba que la API está arrancada (`uvicorn wcm_api.main:app`) "
                    "y que API_URL en .env apunta correctamente."
                ),
            ) from e
        except httpx.TimeoutException as e:
            raise CliApiError(
                f"Timeout esperando al API ({self.config.timeout_s}s).",
                hint="Aumenta WCM_CLI_TIMEOUT_S o investiga la lentitud del servidor.",
            ) from e

        if response.status_code in expect_status:
            if response.status_code == 204 or not response.content:
                return None
            return response.json()

        # Mapping del envelope de error del API → CliError
        self._raise_from_response(response)
        return None  # unreachable

    @staticmethod
    def _raise_from_response(response: httpx.Response) -> None:
        try:
            body = response.json()
            err = body.get("error", {})
            code = err.get("code", "unknown")
            message = err.get("message", response.text[:200] or "Error sin detalle")
        except (ValueError, KeyError):
            code = "unknown"
            message = response.text[:200] or f"HTTP {response.status_code}"

        if response.status_code == 401:
            raise CliAuthError(
                f"No autorizado: {message}",
                hint="Token expirado o credenciales inválidas. Ejecuta `wcm login`.",
            )
        if response.status_code == 403:
            raise CliAuthError(
                f"Acceso denegado: {message}",
                hint="Tu rol no permite esta operación. Contacta con el admin.",
            )
        raise CliApiError(
            f"API HTTP {response.status_code} ({code}): {message}",
            hint=(
                "Revisa los logs del API o el panel /errors para más contexto."
                if response.status_code >= 500 else None
            ),
        )

    # ---------- verbs ----------

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)
