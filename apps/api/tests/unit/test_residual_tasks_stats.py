"""Tests de `GET /api/v1/residual-tasks/stats`.

9 buckets: total, 5 status counts, blocking_go_live, distinct_projects,
estimated_minutes_pending (suma de minutos de tareas no DONE/SKIPPED).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wire(
    fake_session: MagicMock,
    *,
    total: int,
    open_: int,
    in_progress: int,
    blocked: int,
    done: int,
    skipped: int,
    blocking_go_live: int,
    distinct_projects: int,
    estimated_minutes_pending: int,
) -> None:
    """Configura las 9 ejecuciones SQL en orden del código."""
    results = [
        MagicMock(scalar_one=MagicMock(return_value=total)),
        MagicMock(scalar_one=MagicMock(return_value=open_)),
        MagicMock(scalar_one=MagicMock(return_value=in_progress)),
        MagicMock(scalar_one=MagicMock(return_value=blocked)),
        MagicMock(scalar_one=MagicMock(return_value=done)),
        MagicMock(scalar_one=MagicMock(return_value=skipped)),
        MagicMock(scalar_one=MagicMock(return_value=blocking_go_live)),
        MagicMock(scalar_one=MagicMock(return_value=distinct_projects)),
        MagicMock(scalar_one=MagicMock(return_value=estimated_minutes_pending)),
    ]
    fake_session.execute = AsyncMock(side_effect=results)


@pytest.mark.asyncio
async def test_stats_shape_canonica(
    client, fake_session, operator_token
) -> None:
    _wire(
        fake_session,
        total=18, open_=8, in_progress=2, blocked=1, done=6, skipped=1,
        blocking_go_live=4, distinct_projects=3,
        estimated_minutes_pending=240,
    )
    resp = await client.get(
        "/api/v1/residual-tasks/stats", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "total": 18,
        "open": 8,
        "in_progress": 2,
        "blocked": 1,
        "done": 6,
        "skipped": 1,
        "blocking_go_live": 4,
        "distinct_projects": 3,
        "estimated_minutes_pending": 240,
    }


@pytest.mark.asyncio
async def test_stats_viewer_puede_leer(
    client, fake_session, viewer_token
) -> None:
    """`/residual-tasks/stats` es any_user (incluido viewer): info
    operativa de progreso, sin datos sensibles."""
    _wire(
        fake_session,
        total=0, open_=0, in_progress=0, blocked=0, done=0, skipped=0,
        blocking_go_live=0, distinct_projects=0,
        estimated_minutes_pending=0,
    )
    resp = await client.get(
        "/api/v1/residual-tasks/stats", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stats_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/residual-tasks/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_estimated_minutes_excluye_done_y_skipped(
    client, fake_session, operator_token
) -> None:
    """Verifica vía SQL compilado que el WHERE de estimated_minutes
    excluye DONE y SKIPPED (los completados no cuentan como pendiente)."""
    _wire(
        fake_session,
        total=10, open_=5, in_progress=2, blocked=1, done=1, skipped=1,
        blocking_go_live=0, distinct_projects=1,
        estimated_minutes_pending=180,
    )
    resp = await client.get(
        "/api/v1/residual-tasks/stats", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    # La 9ª llamada (índice 8) es la del estimated_minutes_pending.
    stmt = fake_session.execute.call_args_list[8].args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "estimated_minutes" in sql.lower()
    assert "not in" in sql.lower()
    assert "done" in sql.lower()
    assert "skipped" in sql.lower()
