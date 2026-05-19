"""Adapter Wix REST API v1/v3 (Wix Headless) — v0.18.0.

Solo cubre lo necesario para enriquecer el scraping origen cuando el
cliente nos proporciona API key + site_id:

- `list_page_urls()` → URLs canónicas de las páginas del site. Mejor
  que el BFS por links del HTML público, porque incluye páginas que
  el menú no enlaza directamente.
- `list_products()` → catálogo Wix Stores si está activo (futuro;
  esqueleto presente con NotImplementedError documentado).

NO descarga HTML — el HTML público sigue siendo el que un visitante
real ve. El adapter es complementario al fetch HTTP normal: aporta
la lista canónica de URLs.

Credenciales: header `Authorization: <api_key>` + `wix-site-id: <id>`.
Wix REST v3 (Wix Headless). Rate limit: 60 req/min para la free tier.

Errores tipados — el caller decide si caer a Playwright o seguir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("wcm.worker.wix_api")

WIX_BASE_URL = "https://www.wixapis.com"
DEFAULT_TIMEOUT_S = 15.0


class WixApiError(Exception):
    """Base de los errores del adapter Wix."""


class WixApiAuthError(WixApiError):
    """401/403 — api_key inválida o sin permisos suficientes."""


class WixApiNotFoundError(WixApiError):
    """404 — site_id incorrecto o recurso no existe."""


class WixApiRateLimitError(WixApiError):
    """429 — exceder rate limit de la API."""


@dataclass
class WixPageInfo:
    """Información mínima de una página Wix para sembrar el scraping."""

    page_id: str
    url: str
    title: str | None
    is_homepage: bool


class WixApiClient:
    """Cliente async para Wix REST API. Usar como context manager."""

    def __init__(
        self,
        *,
        api_key: str,
        site_id: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if not api_key or not site_id:
            raise ValueError("WixApiClient requiere api_key y site_id no vacíos")
        self.api_key = api_key
        self.site_id = site_id
        self._timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WixApiClient:
        self._client = httpx.AsyncClient(
            base_url=WIX_BASE_URL,
            timeout=self._timeout_s,
            headers={
                "Authorization": self.api_key,
                "wix-site-id": self.site_id,
                "Accept": "application/json",
                "User-Agent": "WebcafeinaMigrator/0.1 (wix-api)",
            },
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("WixApiClient: usar como `async with WixApiClient(...)`")
        return self._client

    async def list_page_urls(self) -> list[WixPageInfo]:
        """Lista las páginas del site. Devuelve URLs canónicas para
        sembrar el scraping. Llama a `/site-properties/v4/properties` para
        obtener el dominio + `/site-pages/v1/pages` para las páginas."""
        # 1. Resolver dominio canónico.
        domain = await self._get_site_domain()

        # 2. Listar páginas (paginación cursor-based; tomamos las primeras 100).
        params = {"paging.limit": "100"}
        response = await self._http.get("/site-pages/v1/pages", params=params)
        self._raise_for_status(response)
        body = response.json()
        pages = body.get("pages", [])

        out: list[WixPageInfo] = []
        for p in pages:
            page_url_suffix = p.get("pageUriSEO") or p.get("pageId") or ""
            is_home = bool(p.get("isHomePage"))
            url = f"https://{domain}/" if is_home else f"https://{domain}/{page_url_suffix.lstrip('/')}"
            out.append(
                WixPageInfo(
                    page_id=p.get("id") or p.get("pageId") or "",
                    url=url,
                    title=p.get("title"),
                    is_homepage=is_home,
                )
            )
        return out

    async def _get_site_domain(self) -> str:
        """Devuelve el dominio canónico del site (premium o subdominio wixsite)."""
        response = await self._http.get("/site-properties/v4/properties")
        self._raise_for_status(response)
        body = response.json()
        props = body.get("properties") or body
        # Wix puede devolver `multilingual.defaultLanguage` y `siteDisplayName`;
        # el dominio principal viene en `domain` o `publishedDomain`.
        domain = (
            props.get("publishedDomain")
            or props.get("primaryDomain")
            or props.get("domain")
            or f"{self.site_id}.wixsite.com"
        )
        if isinstance(domain, dict):
            domain = domain.get("hostname") or f"{self.site_id}.wixsite.com"
        return str(domain).strip("/").removeprefix("https://").removeprefix("http://")

    async def list_products(self) -> list[dict[str, Any]]:
        """Catálogo Wix Stores. NO implementado en v0.18.0 — esqueleto
        para v0.19.0+ cuando integremos productos directamente."""
        raise NotImplementedError(
            "WixApiClient.list_products: pendiente para futuro sprint. "
            "Actualmente WooMigratorAgent lee `woo_products` poblado por "
            "el extractor genérico."
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        s = response.status_code
        if 200 <= s < 300:
            return
        body = response.text[:300]
        if s in (401, 403):
            raise WixApiAuthError(f"Wix API auth {s}: {body}")
        if s == 404:
            raise WixApiNotFoundError(f"Wix API 404 sobre {response.request.url}: {body}")
        if s == 429:
            raise WixApiRateLimitError(f"Wix API rate-limited (429): {body}")
        raise WixApiError(f"Wix API {s} sobre {response.request.url}: {body}")
