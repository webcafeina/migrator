"""Tests del router /health."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_ok(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_calls_db_select_1(client, fake_session) -> None:
    # session.execute returns AsyncMock — no levanta excepción → ready ok
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"
    fake_session.execute.assert_awaited_once()
