"""Tests del WebflowApiClient (v0.18.0). Espejo de test_wix_api.py."""

from __future__ import annotations

import httpx
import pytest
import respx

from wcm_worker.integrations.webflow_api import (
    WEBFLOW_BASE_URL,
    WebflowApiAuthError,
    WebflowApiClient,
    WebflowApiError,
    WebflowApiNotFoundError,
    WebflowApiRateLimitError,
)


def test_init_rechaza_credenciales_vacias() -> None:
    with pytest.raises(ValueError, match="no vacíos"):
        WebflowApiClient(api_token="", site_id="x")
    with pytest.raises(ValueError, match="no vacíos"):
        WebflowApiClient(api_token="x", site_id="")


@pytest.mark.asyncio
async def test_list_page_urls_happy_path_dominio_custom() -> None:
    site_id = "site-abc-123"
    with respx.mock(base_url=WEBFLOW_BASE_URL) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": site_id,
                    "customDomains": [{"url": "miweb.com", "name": "miweb.com"}],
                    "defaultDomain": "miweb.webflow.io",
                },
            )
        )
        router.get(f"/sites/{site_id}/pages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "pages": [
                        {"id": "home1", "slug": "", "title": "Inicio"},
                        {"id": "p2", "slug": "contacto", "title": "Contacto"},
                    ]
                },
            )
        )
        async with WebflowApiClient(api_token="t" * 30, site_id=site_id) as client:
            pages = await client.list_page_urls()

    assert len(pages) == 2
    urls = [p.url for p in pages]
    assert "https://miweb.com/" in urls
    assert "https://miweb.com/contacto" in urls
    assert pages[0].is_homepage is True


@pytest.mark.asyncio
async def test_list_page_urls_fallback_subdominio_webflow_io() -> None:
    site_id = "site-abc-123"
    with respx.mock(base_url=WEBFLOW_BASE_URL, assert_all_called=False) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(
                200,
                json={"id": site_id, "customDomains": [], "defaultDomain": "ejemplo.webflow.io"},
            )
        )
        async with WebflowApiClient(api_token="t" * 30, site_id=site_id) as client:
            domain = await client._get_site_domain()

    assert domain == "ejemplo.webflow.io"


@pytest.mark.asyncio
async def test_auth_error_401() -> None:
    site_id = "site-1"
    with respx.mock(base_url=WEBFLOW_BASE_URL) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(401, text="invalid token")
        )
        async with WebflowApiClient(api_token="bad" * 10, site_id=site_id) as client:
            with pytest.raises(WebflowApiAuthError, match="401"):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_404_site_id_incorrecto() -> None:
    site_id = "wrong"
    with respx.mock(base_url=WEBFLOW_BASE_URL) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(404, text="site not found")
        )
        async with WebflowApiClient(api_token="t" * 30, site_id=site_id) as client:
            with pytest.raises(WebflowApiNotFoundError, match="404"):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_429_rate_limit() -> None:
    site_id = "site-1"
    with respx.mock(base_url=WEBFLOW_BASE_URL) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(429, text="rate limit")
        )
        async with WebflowApiClient(api_token="t" * 30, site_id=site_id) as client:
            with pytest.raises(WebflowApiRateLimitError):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_500_lanza_generico() -> None:
    site_id = "site-1"
    with respx.mock(base_url=WEBFLOW_BASE_URL) as router:
        router.get(f"/sites/{site_id}").mock(
            return_value=httpx.Response(500, text="server error")
        )
        async with WebflowApiClient(api_token="t" * 30, site_id=site_id) as client:
            with pytest.raises(WebflowApiError):
                await client.list_page_urls()


@pytest.mark.asyncio
async def test_list_collections_lanza_notimplemented() -> None:
    async with WebflowApiClient(api_token="t" * 30, site_id="site-1") as client:
        with pytest.raises(NotImplementedError, match="futuro sprint"):
            await client.list_collections()
