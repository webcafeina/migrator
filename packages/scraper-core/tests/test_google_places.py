"""Tests del cliente Google Places (legacy API) — todos con respx,
sin tocar la API real."""

from __future__ import annotations

import httpx
import pytest

from wcm_scraper_core.cache import InMemoryCache
from wcm_scraper_core.directories.google_places import (
    DETAIL_FIELDS,
    GooglePlacesClient,
    GooglePlacesError,
    GooglePlacesQuotaExceeded,
    _cache_key,
    _parse_text_search_result,
)


def _build_client(*, http: httpx.Client | None = None) -> GooglePlacesClient:
    return GooglePlacesClient(
        api_key="test-key",
        cache=InMemoryCache(),
        http_client=http,
        retry_base_delay_s=0.001,  # ⚡ no esperar en tests
    )


class _FakeTransport(httpx.MockTransport):
    """Wrapper para responder con una secuencia de respuestas."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)
        super().__init__(self._handler)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        return next(self._responses)


def test_client_rejects_empty_api_key() -> None:
    with pytest.raises(GooglePlacesError, match="MISSING_API_KEY"):
        GooglePlacesClient(api_key="")


def test_text_search_yields_normalized_results() -> None:
    payload = {
        "status": "OK",
        "results": [
            {
                "place_id": "abc",
                "name": "Bar Pepe",
                "website": "https://barpepe.es",
                "formatted_address": "Cáceres",
                "types": ["restaurant", "food"],
                "rating": 4.5,
                "user_ratings_total": 120,
            },
            {
                "place_id": "def",
                "name": "Sin web",
                "formatted_address": "Cáceres",
                "types": ["restaurant"],
            },
        ],
    }
    transport = _FakeTransport([httpx.Response(200, json=payload)])
    client = _build_client(http=httpx.Client(transport=transport))

    results = list(client.text_search("restaurantes en Cáceres", max_pages=1))

    assert len(results) == 2
    assert results[0].name == "Bar Pepe"
    assert results[0].website == "https://barpepe.es"
    assert results[0].has_website is True
    assert results[1].has_website is False
    assert "restaurant" in results[0].types


def test_text_search_caches_per_query() -> None:
    payload = {"status": "OK", "results": []}
    transport = _FakeTransport([httpx.Response(200, json=payload)])
    cache = InMemoryCache()
    client = GooglePlacesClient(
        api_key="k", cache=cache, http_client=httpx.Client(transport=transport),
        retry_base_delay_s=0.001,
    )

    list(client.text_search("hola", max_pages=1))
    # 2ª llamada idéntica no debe disparar HTTP (transport quedaría vacío)
    list(client.text_search("hola", max_pages=1))


def test_quota_exceeded_raises_typed() -> None:
    payload = {"status": "OVER_QUERY_LIMIT", "error_message": "quota"}
    transport = _FakeTransport([httpx.Response(200, json=payload)])
    client = _build_client(http=httpx.Client(transport=transport))

    with pytest.raises(GooglePlacesQuotaExceeded):
        list(client.text_search("x", max_pages=1))


def test_request_denied_no_retry() -> None:
    payload = {"status": "REQUEST_DENIED", "error_message": "key invalid"}
    transport = _FakeTransport([httpx.Response(200, json=payload)])
    client = _build_client(http=httpx.Client(transport=transport))

    with pytest.raises(GooglePlacesError, match="REQUEST_DENIED"):
        list(client.text_search("x", max_pages=1))


def test_http_429_retries_then_quota_error() -> None:
    transport = _FakeTransport([
        httpx.Response(429, text="rate"),
        httpx.Response(429, text="rate"),
        httpx.Response(429, text="rate"),
    ])
    client = _build_client(http=httpx.Client(transport=transport))
    with pytest.raises(GooglePlacesQuotaExceeded):
        list(client.text_search("x", max_pages=1))


def test_place_details_returns_none_on_not_found() -> None:
    payload = {"status": "NOT_FOUND"}
    transport = _FakeTransport([httpx.Response(200, json=payload)])
    client = _build_client(http=httpx.Client(transport=transport))

    assert client.place_details("ghost-id") is None


def test_place_details_uses_field_mask() -> None:
    """El parámetro `fields` que se envía a Google debe ser nuestra constante."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"status": "OK", "result": {"place_id": "x", "name": "n"}})

    client = _build_client(http=httpx.Client(transport=httpx.MockTransport(handler)))
    result = client.place_details("x")
    assert result is not None
    assert "fields=" in str(captured[0].url)
    # Verificamos que pedimos justo el set que documentamos.
    qs = dict(httpx.URL(str(captured[0].url)).params.multi_items())
    assert qs["fields"] == DETAIL_FIELDS


def test_cache_key_excludes_api_key() -> None:
    """La cache key NO debe incluir el `key=` — riesgo de filtración."""
    k1 = _cache_key("/textsearch/json", {"query": "x", "key": "SECRET-A"})
    k2 = _cache_key("/textsearch/json", {"query": "x", "key": "SECRET-B"})
    assert k1 == k2  # key irrelevante → mismo cache hit


def test_parse_handles_missing_fields_gracefully() -> None:
    result = _parse_text_search_result({"place_id": "x", "name": "y"})
    assert result.place_id == "x"
    assert result.website is None
    assert result.phone is None
    assert result.types == ()
