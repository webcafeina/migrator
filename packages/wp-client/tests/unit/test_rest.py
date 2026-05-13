"""Tests unit del WpRestClient con respx (mocks httpx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.errors import (
    WpAuthError,
    WpNotFoundError,
    WpRateLimitError,
    WpRestError,
    WpSchemaError,
)
from wcm_wp_client.rest import WpRestClient


@pytest.mark.asyncio
async def test_list_pages_returns_array(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "slug": "home"}])
        )
        async with WpRestClient(fake_config) as client:
            pages = await client.list_pages()
    assert len(pages) == 1
    assert pages[0]["slug"] == "home"


@pytest.mark.asyncio
async def test_list_pages_non_array_raises_schema_error(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(
            return_value=httpx.Response(200, json={"oops": "not a list"})
        )
        async with WpRestClient(fake_config) as client:
            with pytest.raises(WpSchemaError):
                await client.list_pages()


@pytest.mark.asyncio
async def test_401_raises_auth_error_no_retry(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        route = router.get("/wp/v2/pages").mock(
            return_value=httpx.Response(401, json={"code": "rest_not_logged_in"})
        )
        async with WpRestClient(fake_config) as client:
            with pytest.raises(WpAuthError):
                await client.list_pages()
        assert route.call_count == 1  # NO retry on 401


@pytest.mark.asyncio
async def test_404_raises_not_found_no_retry(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        route = router.get("/wp/v2/pages/999").mock(return_value=httpx.Response(404))
        async with WpRestClient(fake_config) as client:
            with pytest.raises(WpNotFoundError):
                await client._request("GET", "/wp/v2/pages/999")
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_429_retries_then_raises_rate_limit(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        # 3 intentos → 3 respuestas 429
        route = router.get("/wp/v2/pages").mock(
            return_value=httpx.Response(429, headers={"retry-after": "2"})
        )
        async with WpRestClient(fake_config, max_retry_attempts=3) as client:
            with pytest.raises(WpRateLimitError) as exc_info:
                await client.list_pages()
        assert route.call_count == 3
        assert exc_info.value.retry_after_s == 2.0


@pytest.mark.asyncio
async def test_500_then_200_succeeds(fake_config: WpClientConfig) -> None:
    responses = [httpx.Response(500), httpx.Response(200, json=[])]
    call_count = {"n": 0}

    def side_effect(_request: httpx.Request) -> httpx.Response:
        i = call_count["n"]
        call_count["n"] += 1
        return responses[i]

    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(side_effect=side_effect)
        async with WpRestClient(fake_config, max_retry_attempts=3) as client:
            pages = await client.list_pages()
    assert pages == []
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_generic_5xx_after_retries_raises_rest_error(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(return_value=httpx.Response(502))
        async with WpRestClient(fake_config, max_retry_attempts=2) as client:
            with pytest.raises(WpRestError) as exc_info:
                await client.list_pages()
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_upsert_page_by_slug_creates_when_missing(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(return_value=httpx.Response(200, json=[]))
        create = router.post("/wp/v2/pages").mock(
            return_value=httpx.Response(201, json={"id": 42, "slug": "nueva"})
        )
        async with WpRestClient(fake_config) as client:
            page = await client.upsert_page_by_slug(
                {"slug": "nueva", "title": "Nueva", "status": "publish"}
            )
    assert page["id"] == 42
    assert create.call_count == 1


@pytest.mark.asyncio
async def test_upsert_page_by_slug_updates_when_exists(fake_config: WpClientConfig) -> None:
    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(
            return_value=httpx.Response(200, json=[{"id": 99, "slug": "home"}])
        )
        update = router.post("/wp/v2/pages/99").mock(
            return_value=httpx.Response(200, json={"id": 99, "slug": "home", "title": "Inicio"})
        )
        async with WpRestClient(fake_config) as client:
            page = await client.upsert_page_by_slug(
                {"slug": "home", "title": "Inicio"}
            )
    assert page["id"] == 99
    assert update.call_count == 1


@pytest.mark.asyncio
async def test_upsert_page_requires_slug(fake_config: WpClientConfig) -> None:
    async with WpRestClient(fake_config) as client:
        with pytest.raises(WpSchemaError):
            await client.upsert_page_by_slug({"title": "sin slug"})


@pytest.mark.asyncio
async def test_bricks_import_writes_meta_key(fake_config: WpClientConfig) -> None:
    captured: dict[str, object] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"id": 1})

    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.post("/wp/v2/pages/1").mock(side_effect=capture)
        async with WpRestClient(fake_config) as client:
            await client.bricks_import_page(1, [{"id": "abc123", "name": "section"}])

    import json as _json

    body = _json.loads(captured["body"])
    assert body["meta"]["_bricks_page_content_2"][0]["name"] == "section"


@pytest.mark.asyncio
async def test_bulk_upsert_collects_successes_and_failures(fake_config: WpClientConfig) -> None:
    pages = [
        {"slug": "a", "title": "A"},
        {"slug": "b", "title": "B"},
        {"slug": "c", "title": "C"},
    ]

    def list_handler(request: httpx.Request) -> httpx.Response:
        slug = request.url.params.get("slug")
        return httpx.Response(200, json=[])  # ninguna existe → todo create

    def create_handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.read())
        if body["slug"] == "b":
            return httpx.Response(400, json={"code": "bad_input"})
        return httpx.Response(201, json={"id": ord(body["slug"]), "slug": body["slug"]})

    with respx.mock(base_url=fake_config.rest_endpoint) as router:
        router.get("/wp/v2/pages").mock(side_effect=list_handler)
        router.post("/wp/v2/pages").mock(side_effect=create_handler)

        async with WpRestClient(fake_config) as client:
            result = await client.bulk_upsert_pages_by_slug(pages, batch_size=3)

    assert result.ok_count == 2
    assert result.failed_count == 1
    assert result.failures[0][0]["slug"] == "b"
