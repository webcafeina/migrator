"""Cliente WP REST API.

Skill: `wp-rest-bulk`. Autenticación: Application Password (basic auth).
Soporta sandbox con cert auto-firmado (Local) vía `verify_ssl=False`.

Patrones aplicados:
- Idempotencia por slug/sku al hacer upsert de post/page/producto.
- Retries con backoff exponencial en 408/429/500/502/503/504 + respeto a
  Retry-After.
- Errores tipados: WpAuthError (401/403), WpNotFoundError (404),
  WpRateLimitError (429/503 con Retry-After), WpSchemaError (payload mal),
  WpRestError genérico.
- Bulk operations: insertar en batches con `BulkResult` agregado.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.errors import (
    WpAuthError,
    WpBulkPartialError,
    WpNotFoundError,
    WpRateLimitError,
    WpRestError,
    WpSchemaError,
)
from wcm_wp_client.retries import RETRIABLE_STATUS_CODES, retry_async

log = logging.getLogger("wcm.wp_client.rest")


@dataclass
class BulkResult:
    successes: list[dict[str, Any]] = field(default_factory=list)
    failures: list[tuple[dict[str, Any], Exception]] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return len(self.successes)

    @property
    def failed_count(self) -> int:
        return len(self.failures)


class _RetriableRestSignal(Exception):
    """Marcador interno para que `retry_async` capture solo los 4xx/5xx
    transitorios sin reintentar errores definitivos como 401/404."""

    def __init__(self, status: int, retry_after_s: float | None = None) -> None:
        self.status = status
        self.retry_after_s = retry_after_s


class WpRestClient:
    """Cliente REST. Construir con `WpRestClient(config)` y usar como
    async context manager para gestión del httpx.AsyncClient subyacente.
    """

    def __init__(
        self,
        config: WpClientConfig,
        *,
        timeout_s: float = 30.0,
        max_retry_attempts: int = 3,
    ) -> None:
        self.config = config
        self._timeout_s = timeout_s
        self._max_retry_attempts = max_retry_attempts
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WpRestClient":
        token = base64.b64encode(
            f"{self.config.rest_user}:{self.config.normalized_app_password}".encode()
        ).decode()
        self._client = httpx.AsyncClient(
            base_url=self.config.rest_endpoint,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "User-Agent": "WebcafeinaMigrator/0.1 (REST client)",
            },
            timeout=self._timeout_s,
            verify=self.config.verify_ssl,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("WpRestClient: usar como `async with WpRestClient(cfg)`")
        return self._client

    # ---------- core request con retries + error mapping ----------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        async def _do() -> httpx.Response:
            response = await self._http.request(
                method, path,
                params=params, json=json, files=files, data=data, headers=headers,
            )
            self._raise_for_status(response)
            return response

        try:
            return await retry_async(
                _do,
                max_attempts=self._max_retry_attempts,
                is_retriable=lambda e: isinstance(e, _RetriableRestSignal),
                on_retry=lambda attempt, delay, exc: log.warning(
                    "rest_retry", extra={"attempt": attempt, "delay_s": delay, "status": getattr(exc, "status", None)}
                ),
            )
        except _RetriableRestSignal as e:
            # Retries agotados — convertir señal interna a error público tipado
            if e.status in (429, 503):
                raise WpRateLimitError(
                    f"REST {e.status} tras {self._max_retry_attempts} reintentos",
                    status_code=e.status,
                    retry_after_s=e.retry_after_s,
                ) from None
            raise WpRestError(
                f"REST {e.status} tras {self._max_retry_attempts} reintentos",
                status_code=e.status,
            ) from None

    def _raise_for_status(self, response: httpx.Response) -> None:
        s = response.status_code
        if 200 <= s < 300:
            return
        # Mapping selectivo
        if s in (401, 403):
            raise WpAuthError(
                f"REST auth failed ({s}) on {response.request.url}",
                status_code=s, body=response.text[:500],
            )
        if s == 404:
            raise WpNotFoundError(
                f"REST 404 on {response.request.url}",
                status_code=s, body=response.text[:500],
            )
        if s in (429, 503):
            retry_after = response.headers.get("retry-after")
            try:
                ra = float(retry_after) if retry_after else None
            except ValueError:
                ra = None
            # Marcar para retry, pero exponer el WpRateLimitError tras agotar
            raise _RetriableRestSignal(s, ra)
        if s in RETRIABLE_STATUS_CODES:
            raise _RetriableRestSignal(s)
        raise WpRestError(
            f"REST {s} on {response.request.url}",
            status_code=s, body=response.text[:500],
        )

    # ---------- pages/posts ----------

    async def list_pages(self, **params: Any) -> list[dict[str, Any]]:
        r = await self._request("GET", "/wp/v2/pages", params=params)
        body = r.json()
        if not isinstance(body, list):
            raise WpSchemaError("list_pages: respuesta no es array")
        return body

    async def get_page_by_slug(self, slug: str) -> dict[str, Any] | None:
        pages = await self.list_pages(slug=slug, per_page=1, status="any")
        return pages[0] if pages else None

    async def create_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._request("POST", "/wp/v2/pages", json=payload)
        return r.json()

    async def update_page(self, post_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._request("POST", f"/wp/v2/pages/{post_id}", json=payload)
        return r.json()

    async def delete_page(self, post_id: int, *, force: bool = True) -> dict[str, Any]:
        r = await self._request("DELETE", f"/wp/v2/pages/{post_id}", params={"force": force})
        return r.json()

    async def upsert_page_by_slug(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Idempotente por slug. Si existe, update; si no, create."""
        slug = payload.get("slug")
        if not slug:
            raise WpSchemaError("upsert_page_by_slug requiere `slug` en payload")
        existing = await self.get_page_by_slug(slug)
        if existing:
            return await self.update_page(existing["id"], payload)
        return await self.create_page(payload)

    # ---------- media ----------

    async def upload_media(
        self,
        file_path: Path,
        *,
        alt_text: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Sube un fichero al Media Library. Devuelve el attachment.

        Usa multipart con header Content-Disposition. Tras la subida,
        actualiza alt_text/title si se proporcionan (WP REST no acepta
        alt_text en el POST inicial).
        """
        path = Path(file_path)
        if not path.exists():
            raise WpSchemaError(f"upload_media: fichero no existe: {path}")

        with path.open("rb") as fh:
            files = {"file": (path.name, fh, _guess_mime(path))}
            headers = {"Content-Disposition": f'attachment; filename="{path.name}"'}
            r = await self._request("POST", "/wp/v2/media", files=files, headers=headers)
        attachment = r.json()

        # alt_text y title via PUT separado (REST limitation)
        if alt_text is not None or title is not None:
            patch: dict[str, Any] = {}
            if alt_text is not None:
                patch["alt_text"] = alt_text
            if title is not None:
                patch["title"] = title
            r2 = await self._request("POST", f"/wp/v2/media/{attachment['id']}", json=patch)
            attachment = r2.json()

        return attachment

    # ---------- bulk ----------

    async def bulk_upsert_pages_by_slug(
        self,
        pages: list[dict[str, Any]],
        *,
        batch_size: int = 10,
        strict: bool = False,
    ) -> BulkResult:
        """Bulk upsert por slug. Procesa en batches con concurrencia limitada.

        `strict=True`: si un batch falla, intenta rollback (DELETE de los
        ya creados en ese batch); luego lanza WpBulkPartialError.
        `strict=False` (default): sigue con el siguiente item, registra
        failures y devuelve resultado.
        """
        result = BulkResult()
        for i in range(0, len(pages), batch_size):
            batch = pages[i : i + batch_size]
            created_in_batch: list[int] = []
            try:
                tasks = [self.upsert_page_by_slug(p) for p in batch]
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
                for src, outcome in zip(batch, outcomes):
                    if isinstance(outcome, Exception):
                        if strict:
                            raise outcome
                        result.failures.append((src, outcome))
                    else:
                        result.successes.append(outcome)
                        created_in_batch.append(outcome["id"])
            except Exception as e:
                # En strict, intentar rollback del batch
                if strict and created_in_batch:
                    for pid in created_in_batch:
                        try:
                            await self.delete_page(pid)
                        except Exception:  # pragma: no cover
                            pass
                raise WpBulkPartialError(
                    f"bulk batch failed at i={i}: {e}",
                    successes=result.successes,
                    failures=result.failures,
                ) from e
        return result

    # ---------- yoast / bricks / redirects ----------

    async def upsert_yoast_meta(self, post_id: int, meta: dict[str, Any]) -> dict[str, Any]:
        """Inyecta meta SEO Yoast en un post.

        WP REST acepta `meta` en POST sobre el post; Yoast registra las
        meta keys `_yoast_wpseo_*` como visibles vía REST si está activo
        el plugin con su extensión Yoast SEO REST API.
        """
        return await self.update_page(post_id, {"meta": meta})

    async def bricks_import_page(self, post_id: int, bricks_json: list[dict[str, Any]]) -> dict[str, Any]:
        """Inyecta el contenido Bricks en el post meta `_bricks_page_content_2`.

        NOTA: el endpoint nativo de Bricks NO está documentado públicamente;
        muchos consumidores escriben directamente el post meta. WP REST
        permite escritura de meta keys "registradas" — Bricks registra esta
        key como `show_in_rest`. Si tu site no lo expone, fallback a wp-cli.
        """
        return await self.update_page(post_id, {"meta": {"_bricks_page_content_2": bricks_json}})

    async def import_redirects(self, redirects: list[dict[str, Any]]) -> BulkResult:
        """Vía plugin Redirection (REST endpoint `/redirection/v1/redirect`).

        Cada redirect: {url, action_type='url', action_data: {url: target}, http_code: 301}
        Sin el plugin activo, devuelve 404 → WpNotFoundError.
        """
        result = BulkResult()
        for r in redirects:
            try:
                response = await self._request(
                    "POST", "/redirection/v1/redirect", json=r
                )
                result.successes.append(response.json())
            except Exception as e:
                result.failures.append((r, e))
        return result


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
        "gif": "image/gif", "svg": "image/svg+xml",
        "pdf": "application/pdf",
        "mp4": "video/mp4", "webm": "video/webm",
        "woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf",
    }.get(suffix, "application/octet-stream")
