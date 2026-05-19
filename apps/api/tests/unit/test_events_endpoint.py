"""Tests del endpoint GET /api/v1/projects/{id}/events (v0.19.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_id: int = 7) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    return p


@pytest.mark.asyncio
async def test_404_si_proyecto_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/projects/99/events", headers=_auth(viewer_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_401_sin_auth(client, fake_session) -> None:
    resp = await client.get("/api/v1/projects/7/events")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_viewer_puede_subscribirse(
    client, fake_session, viewer_token, monkeypatch
) -> None:
    """Cualquier rol autenticado puede escuchar eventos del proyecto."""
    fake_session.get = AsyncMock(return_value=_project_mock())

    # Mockear el generator del servicio para no tocar Redis.
    async def _fake_gen(project_id: int):
        yield b"data: {\"kind\":\"hello\"}\n\n"

    monkeypatch.setattr(
        "wcm_api.routers.projects.subscribe_to_project_events",
        _fake_gen,
    )
    resp = await client.get("/api/v1/projects/7/events", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_503_si_redis_no_responde(
    client, fake_session, viewer_token, monkeypatch
) -> None:
    """Si la suscripción inicial falla, 503 (cliente cae a polling)."""
    fake_session.get = AsyncMock(return_value=_project_mock())

    def _explode(_project_id: int):
        raise ConnectionError("REDIS_URL no configurado")

    monkeypatch.setattr(
        "wcm_api.routers.projects.subscribe_to_project_events",
        _explode,
    )
    resp = await client.get("/api/v1/projects/7/events", headers=_auth(viewer_token))
    assert resp.status_code == 503
