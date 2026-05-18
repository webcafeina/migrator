"""Tests de `GET /api/v1/projects/stats`.

Análogo a `/leads/stats` (v0.4.0). 8 buckets agregados: total, queued,
running, blocked, completed, failed_or_cancelled, distinct_builders,
avg_visual_diff_score.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wire_stats(
    fake_session: MagicMock,
    *,
    total: int,
    queued: int,
    running: int,
    blocked: int,
    completed: int,
    failed_or_cancelled: int,
    distinct_builders: int,
    avg_diff: float | None,
) -> None:
    """Configura las 8 llamadas a `session.execute()` en orden del código."""
    results = [
        MagicMock(scalar_one=MagicMock(return_value=total)),
        MagicMock(scalar_one=MagicMock(return_value=queued)),
        MagicMock(scalar_one=MagicMock(return_value=running)),
        MagicMock(scalar_one=MagicMock(return_value=blocked)),
        MagicMock(scalar_one=MagicMock(return_value=completed)),
        MagicMock(scalar_one=MagicMock(return_value=failed_or_cancelled)),
        MagicMock(scalar_one=MagicMock(return_value=distinct_builders)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=avg_diff)),
    ]
    fake_session.execute = AsyncMock(side_effect=results)


@pytest.mark.asyncio
async def test_stats_shape_y_valores(
    client, fake_session, operator_token
) -> None:
    _wire_stats(
        fake_session,
        total=12,
        queued=2,
        running=3,
        blocked=1,
        completed=5,
        failed_or_cancelled=1,
        distinct_builders=4,
        avg_diff=0.87,
    )
    resp = await client.get(
        "/api/v1/projects/stats", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "total": 12,
        "queued": 2,
        "running": 3,
        "blocked": 1,
        "completed": 5,
        "failed_or_cancelled": 1,
        "distinct_builders": 4,
        "avg_visual_diff_score": 0.87,
    }


@pytest.mark.asyncio
async def test_stats_avg_null_sin_diff(
    client, fake_session, viewer_token
) -> None:
    """Sistema sin proyectos con visual_diff: avg_visual_diff_score = null."""
    _wire_stats(
        fake_session,
        total=0,
        queued=0,
        running=0,
        blocked=0,
        completed=0,
        failed_or_cancelled=0,
        distinct_builders=0,
        avg_diff=None,
    )
    resp = await client.get(
        "/api/v1/projects/stats", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["avg_visual_diff_score"] is None
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_stats_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/projects/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_falled_or_cancelled_agrupa_dos_estados(
    client, fake_session, operator_token
) -> None:
    """`failed_or_cancelled` debe ejecutar UN solo WHERE con IN (..2..)."""
    _wire_stats(
        fake_session,
        total=10,
        queued=0,
        running=0,
        blocked=0,
        completed=7,
        failed_or_cancelled=3,
        distinct_builders=2,
        avg_diff=0.9,
    )
    resp = await client.get(
        "/api/v1/projects/stats", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    # La 6ª llamada (índice 5) es la del bucket failed_or_cancelled.
    stmt = fake_session.execute.call_args_list[5].args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "in (" in sql.lower() or "in(" in sql.lower()
    assert "qa_failed" in sql.lower()
    assert "cancelled" in sql.lower()


@pytest.mark.asyncio
async def test_stats_distinct_builders_excluye_unknown_y_null(
    client, fake_session, operator_token
) -> None:
    _wire_stats(
        fake_session,
        total=5, queued=0, running=0, blocked=0,
        completed=5, failed_or_cancelled=0,
        distinct_builders=3, avg_diff=None,
    )
    resp = await client.get(
        "/api/v1/projects/stats", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    # La 7ª llamada (índice 6) es la del bucket distinct_builders.
    stmt = fake_session.execute.call_args_list[6].args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "builder_source" in sql.lower()
    assert "is not null" in sql.lower()
    assert "unknown" in sql.lower()
