"""Tests de `GET /api/v1/leads/stats`.

Endpoint para alimentar el topbar denso de la pantalla /leads del dashboard.
Devuelve agregados: total, sin contactar, score medio, builders/sectores/
regiones únicos. Mockeamos las 5 ejecuciones SQL con `side_effect`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wire_stats(fake_session: MagicMock, *, total: int, uncontacted: int,
                avg_score: float | None, builders: int, sectors: int, regions: int) -> None:
    """Configura las 6 llamadas a `session.execute()` que hace el endpoint
    en el orden exacto del código (total → uncontacted → avg → builders →
    sectors → regions)."""
    results = [
        MagicMock(scalar_one=MagicMock(return_value=total)),
        MagicMock(scalar_one=MagicMock(return_value=uncontacted)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=avg_score)),
        MagicMock(scalar_one=MagicMock(return_value=builders)),
        MagicMock(scalar_one=MagicMock(return_value=sectors)),
        MagicMock(scalar_one=MagicMock(return_value=regions)),
    ]
    fake_session.execute = AsyncMock(side_effect=results)


@pytest.mark.asyncio
async def test_stats_devuelve_shape_y_valores(client, fake_session, operator_token) -> None:
    _wire_stats(
        fake_session,
        total=29, uncontacted=12, avg_score=41.3,
        builders=5, sectors=4, regions=3,
    )
    resp = await client.get("/api/v1/leads/stats", headers=_auth(operator_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "total": 29,
        "uncontacted": 12,
        "avg_score": 41.3,
        "distinct_builders": 5,
        "distinct_sectors": 4,
        "distinct_regions": 3,
    }


@pytest.mark.asyncio
async def test_stats_avg_null_cuando_no_hay_leads(client, fake_session, viewer_token) -> None:
    """Pipeline recién inicializado: 0 leads → avg_score null y agregados a 0."""
    _wire_stats(
        fake_session,
        total=0, uncontacted=0, avg_score=None,
        builders=0, sectors=0, regions=0,
    )
    resp = await client.get("/api/v1/leads/stats", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["avg_score"] is None
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_stats_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/leads/stats")
    assert resp.status_code == 401
