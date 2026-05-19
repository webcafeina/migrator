"""Tests del WixApiClient (v0.18.0).

Cubre: construcción headers + lifecycle, list_page_urls happy path,
mapping de respuesta JSON, errores tipados (auth/notfound/rate limit),
helper de dominio (premium domain vs subdominio wixsite por defecto).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from wcm_worker.integrations.wix_api import (
    WIX_BASE_URL,
    WixApiAuthError,
    WixApiClient,
    WixApiError,
    WixApiNotFoundError,
    WixApiRateLimitError,
)


def test_init_rechaza_credenciales_vacias() -> None:
    with pytest.raises(ValueError, match="no vacíos"):
        WixApiClient(api_key="", site_id="x")
    with pytest.raises(ValueError, match="no vacíos"):
        WixApiClient(api_key="x", site_id="")


@pytest.mark.asyncio
async def test_list_page_urls_happy_path() -> None:
    site_id = "site-abc-123"
    with respx.mock(base_url=WIX_BASE_URL) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(
                200,
                json={"properties": {"publishedDomain": "miweb.com"}},
            )
        )
        router.get("/site-pages/v1/pages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "pages": [
                        {"id": "home1", "pageUriSEO": "", "isHomePage": True, "title": "Inicio"},
                        {"id": "p2", "pageUriSEO": "contacto", "isHomePage": False, "title": "Contacto"},
                    ]
                },
            )
        )
        async with WixApiClient(api_key="key-1234567890abcdef1234", site_id=site_id) as client:
            pages = await client.list_page_urls()

    assert len(pages) == 2
    urls = [p.url for p in pages]
    assert "https://miweb.com/" in urls
    assert "https://miweb.com/contacto" in urls
    assert pages[0].is_homepage is True


@pytest.mark.asyncio
async def test_list_page_urls_fallback_subdominio_wixsite() -> None:
    """Sin publishedDomain → wixsite por defecto."""
    site_id = "site-abc-123"
    with respx.mock(base_url=WIX_BASE_URL, assert_all_called=False) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(200, json={"properties": {}})
        )
        async with WixApiClient(api_key="key-1234567890abcdef1234", site_id=site_id) as client:
            domain = await client._get_site_domain()

    assert domain == f"{site_id}.wixsite.com"


@pytest.mark.asyncio
async def test_auth_error_lanza_wixapiautherror() -> None:
    with respx.mock(base_url=WIX_BASE_URL) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(401, text="invalid api_key")
        )
        async with WixApiClient(api_key="bad-key-1234567890abcdef", site_id="site-1") as client:
            with pytest.raises(WixApiAuthError, match="401"):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_404_lanza_wixapinotfounderror() -> None:
    with respx.mock(base_url=WIX_BASE_URL) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(404, text="site not found")
        )
        async with WixApiClient(api_key="key-1234567890abcdef1234", site_id="wrong") as client:
            with pytest.raises(WixApiNotFoundError, match="404"):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_429_lanza_ratelimiterror() -> None:
    with respx.mock(base_url=WIX_BASE_URL) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(429, text="rate limit")
        )
        async with WixApiClient(api_key="key-1234567890abcdef1234", site_id="site-1") as client:
            with pytest.raises(WixApiRateLimitError):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_500_lanza_wixapierror_generico() -> None:
    with respx.mock(base_url=WIX_BASE_URL) as router:
        router.get("/site-properties/v4/properties").mock(
            return_value=httpx.Response(500, text="server error")
        )
        async with WixApiClient(api_key="key-1234567890abcdef1234", site_id="site-1") as client:
            with pytest.raises(WixApiError):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_list_products_lanza_notimplemented() -> None:
    async with WixApiClient(api_key="key-1234567890abcdef1234", site_id="site-1") as client:
        with pytest.raises(NotImplementedError, match="futuro sprint"):
            await client.list_products()


def test_uso_fuera_de_context_manager_lanza_runtimeerror() -> None:
    """Acceder a _http sin haber entrado al async with lanza RuntimeError."""
    client = WixApiClient(api_key="x" * 30, site_id="site-1")
    with pytest.raises(RuntimeError, match="async with"):
        _ = client._http
