"""Cliente ClickUp REST API v2.

Operaciones que necesita el sync de residual_tasks:
- `create_task(list_id, title, description, ...)` → devuelve task_id.
- `update_task(task_id, ...)` → patch parcial.
- `close_task(task_id)` → status "complete" (configurable).
- `find_member(name)` → resuelve un username a clickup user_id para assignee.

Diseño:
- Tokens Bearer (env `CLICKUP_API_TOKEN`).
- Lista por defecto `CLICKUP_DEFAULT_LIST_ID` (Microtareas: 900102088242).
- Retries simples sobre 429/5xx con backoff exponencial.
- Errores 4xx (excepto 429) NO se reintentan — son problemas de payload.

ADR-027 documenta el mapping de `residual_tasks` ↔ ClickUp custom fields.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger("wcm.worker.integrations.clickup")

DEFAULT_BASE = "https://api.clickup.com/api/v2"


class ClickupApiError(Exception):
    """Error de la API. Argumentos: (status_code, message, payload)."""

    def __init__(self, status_code: int, message: str, payload: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.payload = payload or {}
        super().__init__(f"ClickUp[{status_code}] {message}")


class ClickupClient:
    """Cliente sincrónico para uso desde Celery workers."""

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = DEFAULT_BASE,
        default_list_id: str | None = None,
        team_id: str | None = None,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        retry_base_delay_s: float = 1.0,
    ) -> None:
        if not api_token:
            raise ClickupApiError(0, "CLICKUP_API_TOKEN vacía")
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.default_list_id = default_list_id
        self.team_id = team_id
        self._http = http_client or httpx.Client(timeout=15.0)
        self._owns_http = http_client is None
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s

    @classmethod
    def from_env(cls) -> ClickupClient | None:
        """Construye desde env. Devuelve None si falta el token (skip)."""
        token = os.environ.get("CLICKUP_API_TOKEN", "").strip()
        if not token:
            return None
        return cls(
            api_token=token,
            default_list_id=os.environ.get("CLICKUP_DEFAULT_LIST_ID"),
            team_id=os.environ.get("CLICKUP_TEAM_ID"),
        )

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> ClickupClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------- public ----------

    def create_task(
        self,
        *,
        list_id: str | None = None,
        title: str,
        description: str = "",
        assignees: list[int] | None = None,
        tags: list[str] | None = None,
        priority: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """POST /list/{list_id}/task. Devuelve el dict completo del task creado."""
        target_list = list_id or self.default_list_id
        if not target_list:
            raise ClickupApiError(0, "list_id no proporcionado y CLICKUP_DEFAULT_LIST_ID vacío")
        body: dict[str, Any] = {"name": title, "description": description}
        if assignees:
            body["assignees"] = assignees
        if tags:
            body["tags"] = tags
        if priority is not None:
            body["priority"] = priority
        if custom_fields:
            body["custom_fields"] = custom_fields
        return self._request("POST", f"/list/{target_list}/task", json=body)

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """PUT /task/{task_id}. Sólo manda los campos pasados."""
        return self._request("PUT", f"/task/{task_id}", json=fields)

    def close_task(self, task_id: str, *, status: str = "complete") -> dict[str, Any]:
        """Marcar como completada. Atajo de update_task con status."""
        return self.update_task(task_id, status=status)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/task/{task_id}")

    def find_member(self, name: str) -> int | None:
        """Resuelve nombre → user_id consultando los miembros del team.

        Búsqueda case-insensitive sobre `username` y `email`. Devuelve None
        si no se encuentra (el caller decide si asignar o dejar sin asignar).
        """
        if not self.team_id:
            return None
        data = self._request("GET", f"/team/{self.team_id}/member")
        members = data.get("members", [])
        lower = name.lower()
        for member in members:
            user = member.get("user", {})
            if user.get("username", "").lower() == lower or user.get("email", "").lower() == lower:
                return int(user.get("id"))
        return None

    # ---------- internals ----------

    def _request(self, method: str, path: str, *, json: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._http.request(method, url, json=json, headers=headers)
            except httpx.RequestError as e:
                if attempt >= self.max_retries:
                    raise ClickupApiError(0, f"network: {e}") from e
                time.sleep(self.retry_base_delay_s * (2 ** (attempt - 1)))
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt >= self.max_retries:
                    raise ClickupApiError(
                        resp.status_code, resp.text[:200] or "retry exhausted"
                    )
                time.sleep(self.retry_base_delay_s * (2 ** (attempt - 1)))
                continue
            if resp.status_code >= 400:
                raise ClickupApiError(
                    resp.status_code, resp.text[:500] or resp.reason_phrase,
                )
            try:
                return resp.json()
            except ValueError:
                return {}
