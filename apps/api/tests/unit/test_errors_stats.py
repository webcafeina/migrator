"""Tests de `GET /api/v1/errors/stats`.

8 buckets agregados en ventana configurable: total + counts por
ErrorSeverity + distinct_components + last_critical_at.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wire(
    fake_session: MagicMock,
    *,
    total: int,
    critical: int,
    error: int,
    warning: int,
    info: int,
    debug: int,
    distinct_components: int,
    last_critical: datetime | None,
) -> None:
    """Configura las 8 llamadas a execute() en orden del código."""
    results = [
        MagicMock(scalar_one=MagicMock(return_value=total)),
        MagicMock(scalar_one=MagicMock(return_value=critical)),
        MagicMock(scalar_one=MagicMock(return_value=error)),
        MagicMock(scalar_one=MagicMock(return_value=warning)),
        MagicMock(scalar_one=MagicMock(return_value=info)),
        MagicMock(scalar_one=MagicMock(return_value=debug)),
        MagicMock(scalar_one=MagicMock(return_value=distinct_components)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=last_critical)),
    ]
    fake_session.execute = AsyncMock(side_effect=results)


@pytest.mark.asyncio
async def test_stats_shape_canonica(client, fake_session, operator_token) -> None:
    last = datetime.now(UTC) - timedelta(hours=2)
    _wire(
        fake_session,
        total=42, critical=1, error=8, warning=12, info=20, debug=1,
        distinct_components=5, last_critical=last,
    )
    resp = await client.get("/api/v1/errors/stats", headers=_auth(operator_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 42
    assert data["critical"] == 1
    assert data["error"] == 8
    assert data["warning"] == 12
    assert data["info"] == 20
    assert data["debug"] == 1
    assert data["distinct_components"] == 5
    assert data["last_critical_at"] is not None


@pytest.mark.asyncio
async def test_stats_last_critical_null_si_sin_criticos(
    client, fake_session, operator_token
) -> None:
    _wire(
        fake_session,
        total=10, critical=0, error=2, warning=5, info=3, debug=0,
        distinct_components=2, last_critical=None,
    )
    resp = await client.get("/api/v1/errors/stats", headers=_auth(operator_token))
    assert resp.status_code == 200
    assert resp.json()["last_critical_at"] is None


@pytest.mark.asyncio
async def test_stats_viewer_no_puede_leer(
    client, fake_session, viewer_token
) -> None:
    """`/errors` y `/errors/stats` son admin/operator only (datos
    sensibles de runtime con posibles stack traces)."""
    resp = await client.get("/api/v1/errors/stats", headers=_auth(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stats_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/errors/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_since_hours_invalido_422(
    client, fake_session, operator_token
) -> None:
    """`since_hours > 24*90` rechazado por Pydantic Query(le=24*90)."""
    resp = await client.get(
        "/api/v1/errors/stats?since_hours=5000",
        headers=_auth(operator_token),
    )
    assert resp.status_code == 422
