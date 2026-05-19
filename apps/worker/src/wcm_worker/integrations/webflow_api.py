"""Adapter Webflow Sites/CMS API v2 — v0.18.0.

Espejo de `wix_api.py` para Webflow. Mismo contrato:

- `list_page_urls()` → URLs canónicas. Mejor que BFS por links del HTML
  público porque incluye páginas no enlazadas desde el menú.
- `list_collections()` → contenidos CMS (futuro; esqueleto).

Credenciales: `Authorization: Bearer <api_token>`. Webflow API v2.
Rate limit: 60 req/min para free tier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("wcm.worker.webflow_api")

WEBFLOW_BASE_URL = "https://api.webflow.com/v2"
DEFAULT_TIMEOUT_S = 15.0


class WebflowApiError(Exception):
    """Base de los errores del adapter Webflow."""


class WebflowApiAuthError(WebflowApiError):
    """401/403 — api_token inválido o sin permisos."""


class WebflowApiNotFoundError(WebflowApiError):
    """404 — site_id incorrecto."""


class WebflowApiRateLimitError(WebflowApiError):
    """429 — rate limit excedido."""


@dataclass
class WebflowPageInfo:
    """Información mínima de una página Webflow para sembrar el scraping."""

    page_id: str
    url: str
    title: str | None
    slug: str
    is_homepage: bool


class WebflowApiClient:
    """Cliente async para Webflow API v2. Usar como context manager."""

    def __init__(
        self,
        *,
        api_token: str,
        site_id: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if not api_token or not site_id:
            raise ValueError("WebflowApiClient requiere api_token y site_id no vacíos")
        self.api_token = api_token
        self.site_id = site_id
        self._timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WebflowApiClient:
        self._client = httpx.AsyncClient(
            base_url=WEBFLOW_BASE_URL,
            timeout=self._timeout_s,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
                "User-Agent": "WebcafeinaMigrator/0.1 (webflow-api)",
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
            raise RuntimeError(
                "WebflowApiClient: usar como `async with WebflowApiClient(...)`"
            )
        return self._client

    async def list_page_urls(self) -> list[WebflowPageInfo]:
        """Listar páginas del site. GET /sites/{site_id} para dominio +
        GET /sites/{site_id}/pages para páginas."""
        domain = await self._get_site_domain()

        response = await self._http.get(f"/sites/{self.site_id}/pages")
        self._raise_for_status(response)
        body = response.json()
        pages = body.get("pages", [])

        out: list[WebflowPageInfo] = []
        for p in pages:
            slug = p.get("slug") or ""
            is_home = slug == "" or slug == "index"
            url = (
                f"https://{domain}/"
                if is_home
                else f"https://{domain}/{slug.lstrip('/')}"
            )
            out.append(
                WebflowPageInfo(
                    page_id=p.get("id", ""),
                    url=url,
                    title=p.get("title") or p.get("seo", {}).get("title"),
                    slug=slug,
                    is_homepage=is_home,
                )
            )
        return out

    async def _get_site_domain(self) -> str:
        """Devuelve el dominio canónico del site (custom o subdominio webflow.io)."""
        response = await self._http.get(f"/sites/{self.site_id}")
        self._raise_for_status(response)
        site = response.json()
        # Webflow devuelve `customDomains` (list) y `defaultDomain` (subdominio webflow.io).
        custom = site.get("customDomains") or []
        if custom:
            first = custom[0]
            if isinstance(first, dict):
                return str(first.get("url") or first.get("name") or "").strip("/")
            return str(first).strip("/")
        default = site.get("defaultDomain") or site.get("shortName")
        if not default:
            return f"{self.site_id}.webflow.io"
        return str(default).removeprefix("https://").removeprefix("http://").strip("/")

    async def list_collections(self) -> list[dict[str, Any]]:
        """Contenidos CMS. NO implementado en v0.18.0 — esqueleto para
        futuros sprints cuando integremos CMS items directamente."""
        raise NotImplementedError(
            "WebflowApiClient.list_collections: pendiente para futuro sprint."
        )

    async def list_orders(self) -> list[dict[str, Any]]:
        """ADR-045 — historial pedidos Webflow Ecommerce. Endpoint:
        GET /sites/{site_id}/orders."""
        r = await self._http.get(f"/sites/{self.site_id}/orders")
        self._raise_for_status(r)
        body = r.json()
        return [self._map_order(o) for o in body.get("orders", [])]

    async def list_coupons(self) -> list[dict[str, Any]]:
        """ADR-045 — descuentos activos Webflow Ecommerce. Endpoint:
        GET /sites/{site_id}/promo_codes (deprecated, pero único en API v2)."""
        r = await self._http.get(f"/sites/{self.site_id}/promo_codes")
        self._raise_for_status(r)
        body = r.json()
        return body.get("promoCodes", body.get("items", []))

    @staticmethod
    def _map_order(o: dict[str, Any]) -> dict[str, Any]:
        """Normaliza shape Webflow → schema woo_orders común."""
        customer = o.get("customerInfo", {}) or {}
        shipping = o.get("shippingAddress", {}) or {}
        billing = o.get("billingAddress", {}) or shipping
        totals = o.get("totals", {}) or {}
        return {
            "external_id": str(o.get("orderId") or o.get("id") or ""),
            "order_number": str(o.get("orderNumber", "")),
            "status": o.get("status", "unknown"),
            "financial_status": o.get("paymentProcessed") and "paid" or "pending",
            "total_amount": totals.get("total"),
            "total_currency": o.get("currency"),
            "customer_email": customer.get("email"),
            "customer_name": customer.get("fullName"),
            "billing_address": billing,
            "shipping_address": shipping,
            "line_items": o.get("purchasedItems", []),
            "placed_at": o.get("acceptedOn") or o.get("orderTime"),
            "payment_method": o.get("paymentMethod"),
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        s = response.status_code
        if 200 <= s < 300:
            return
        body = response.text[:300]
        if s in (401, 403):
            raise WebflowApiAuthError(f"Webflow API auth {s}: {body}")
        if s == 404:
            raise WebflowApiNotFoundError(
                f"Webflow API 404 sobre {response.request.url}: {body}"
            )
        if s == 429:
            raise WebflowApiRateLimitError(f"Webflow API rate-limited (429): {body}")
        raise WebflowApiError(f"Webflow API {s} sobre {response.request.url}: {body}")
