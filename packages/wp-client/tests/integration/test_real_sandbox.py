"""Tests integración contra el sandbox WP real.

Requieren `.env` cargado con `WP_DEFAULT_*`. Si no está, se skippean.

Para cargarlo manualmente desde la raíz del repo:
    set -a; source .env; set +a
    pytest packages/wp-client/tests/integration -m integration -v
"""

from __future__ import annotations

import pytest

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.rest import WpRestClient
from wcm_wp_client.ssh_cli import WpCliSshClient

pytestmark = pytest.mark.integration


# ---------- REST ----------

@pytest.mark.asyncio
async def test_rest_get_users_me(real_config_or_skip: WpClientConfig) -> None:
    async with WpRestClient(real_config_or_skip) as client:
        # Endpoint /users/me responde solo si auth OK
        response = await client._request("GET", "/wp/v2/users/me")
        data = response.json()
        assert data["id"] >= 1


@pytest.mark.asyncio
async def test_rest_list_pages(real_config_or_skip: WpClientConfig) -> None:
    async with WpRestClient(real_config_or_skip) as client:
        pages = await client.list_pages(per_page=5)
    assert isinstance(pages, list)


@pytest.mark.asyncio
async def test_rest_create_and_delete_page(real_config_or_skip: WpClientConfig) -> None:
    payload = {
        "title": "WCM Test Page",
        "slug": "wcm-test-page-delete-me",
        "status": "draft",
        "content": "<p>Created by wp-client integration tests.</p>",
    }
    async with WpRestClient(real_config_or_skip) as client:
        page = await client.create_page(payload)
        try:
            assert page["id"] > 0
            assert page["slug"] == "wcm-test-page-delete-me"
        finally:
            await client.delete_page(page["id"], force=True)


@pytest.mark.asyncio
async def test_rest_upsert_idempotent(real_config_or_skip: WpClientConfig) -> None:
    slug = "wcm-upsert-idempotent"
    payload_v1 = {"slug": slug, "title": "V1", "status": "draft", "content": "v1"}
    payload_v2 = {"slug": slug, "title": "V2", "status": "draft", "content": "v2"}

    async with WpRestClient(real_config_or_skip) as client:
        a = await client.upsert_page_by_slug(payload_v1)
        b = await client.upsert_page_by_slug(payload_v2)
        try:
            assert a["id"] == b["id"], "upsert debe reusar el mismo post"
            assert b["title"]["rendered"] == "V2"
        finally:
            await client.delete_page(a["id"], force=True)


# ---------- WP-CLI ----------

@pytest.mark.asyncio
async def test_cli_core_version(real_config_or_skip: WpClientConfig) -> None:
    async with WpCliSshClient(real_config_or_skip) as cli:
        version = await cli.core_version()
    assert version.split(".")[0].isdigit()


@pytest.mark.asyncio
async def test_cli_core_is_installed_true(real_config_or_skip: WpClientConfig) -> None:
    async with WpCliSshClient(real_config_or_skip) as cli:
        assert await cli.core_is_installed()


@pytest.mark.asyncio
async def test_cli_option_get_siteurl(real_config_or_skip: WpClientConfig) -> None:
    async with WpCliSshClient(real_config_or_skip) as cli:
        siteurl = await cli.option_get("siteurl")
    assert siteurl.startswith(("http://", "https://"))


@pytest.mark.asyncio
async def test_cli_search_replace_dry_run(real_config_or_skip: WpClientConfig) -> None:
    """Dry-run no modifica nada — seguro de ejecutar contra cualquier sandbox."""
    async with WpCliSshClient(real_config_or_skip) as cli:
        result = await cli.search_replace(
            "https://example.invalid-never-matches-xyz/",
            "https://other.invalid-xyz/",
            dry_run=True,
        )
    assert result["dry_run"] is True
    # replacements suele ser 0 con la URL inventada; lo crítico es que el
    # comando se ejecutó sin error y devolvió un int.
    assert isinstance(result["replacements"], int)
    assert result["replacements"] == 0
