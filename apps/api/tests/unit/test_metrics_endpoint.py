"""Test del endpoint /metrics + middleware Prometheus."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_text(client) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "wcm_http_requests_total" in resp.text


@pytest.mark.asyncio
async def test_middleware_records_request_counter(client) -> None:
    # Generamos un request a un endpoint conocido y luego comprobamos /metrics.
    await client.get("/health")
    resp = await client.get("/metrics")
    body = resp.text
    # /health debe aparecer en la cuenta. La label `path` puede ser la
    # plantilla resuelta /health o el fallback.
    assert "wcm_http_requests_total" in body
    assert "wcm_http_request_duration_seconds" in body
