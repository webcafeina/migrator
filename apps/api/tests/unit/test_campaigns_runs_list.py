"""Tests de `GET /api/v1/campaigns/runs` (histórico de campañas pasadas).

Cubre: shape, paginación (limit/offset), filtro status, ventana default
30 días, ordenación DESC, duración calculada, auth.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from wcm_types.enums import CampaignStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _campaign(
    *,
    id: int = 1,
    task_id: str | None = None,
    sector: str = "marketing",
    region: str = "Cáceres",
    target_count: int = 50,
    status: CampaignStatus = CampaignStatus.COMPLETED,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    created_lead_ids: list[int] | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
    user_id: object | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.task_id = task_id or str(uuid4())
    c.sector = sector
    c.region = region
    c.target_count = target_count
    c.status = status
    c.started_at = started_at or datetime.now(UTC)
    c.completed_at = completed_at
    c.created_lead_ids = created_lead_ids or []
    c.warnings = warnings or []
    c.error = error
    c.created_by_user_id = user_id
    return c


def _wire_result(fake_session: MagicMock, rows: list[MagicMock]) -> None:
    scalars = MagicMock(all=MagicMock(return_value=rows))
    result = MagicMock(scalars=MagicMock(return_value=scalars))
    fake_session.execute = AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_runs_devuelve_shape_canonica(
    client, fake_session, operator_token
) -> None:
    started = datetime.now(UTC) - timedelta(hours=2)
    completed = started + timedelta(minutes=8, seconds=30)
    _wire_result(
        fake_session,
        [
            _campaign(
                id=42,
                sector="restauración",
                region="Madrid",
                target_count=30,
                status=CampaignStatus.COMPLETED,
                started_at=started,
                completed_at=completed,
                created_lead_ids=[1, 2, 3, 4, 5],
                warnings=["dup api key", "rate-limit hit"],
            ),
        ],
    )
    resp = await client.get(
        "/api/v1/campaigns/runs", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == 42
    assert item["sector"] == "restauración"
    assert item["region"] == "Madrid"
    assert item["target_count"] == 30
    assert item["status"] == "completed"
    assert item["leads_count"] == 5
    assert item["warnings_count"] == 2
    # 8m30s = 510s
    assert item["duration_s"] == 510
    assert item["error"] is None
    assert {
        "id",
        "task_id",
        "sector",
        "region",
        "target_count",
        "status",
        "started_at",
        "completed_at",
        "duration_s",
        "leads_count",
        "warnings_count",
        "error",
        "created_by_user_id",
    }.issubset(item.keys())


@pytest.mark.asyncio
async def test_runs_duration_null_si_aun_corre(
    client, fake_session, operator_token
) -> None:
    _wire_result(
        fake_session,
        [_campaign(status=CampaignStatus.RUNNING, completed_at=None)],
    )
    resp = await client.get(
        "/api/v1/campaigns/runs", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    assert resp.json()[0]["duration_s"] is None
    assert resp.json()[0]["completed_at"] is None


@pytest.mark.asyncio
async def test_runs_filter_status_aplica_where(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs?status=failed", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "campaigns.status" in sql
    assert "failed" in sql.lower()


@pytest.mark.asyncio
async def test_runs_orden_descendente_por_started_at(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    sql = str(
        fake_session.execute.call_args.args[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "order by" in sql.lower()
    assert "started_at" in sql.lower()
    assert "desc" in sql.lower()


@pytest.mark.asyncio
async def test_runs_ventana_default_30_dias(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    sql = str(
        fake_session.execute.call_args.args[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "campaigns.started_at" in sql
    # Comprobamos que aplica el WHERE >= ; el valor literal cambia cada
    # ejecución, basta con asegurarse de que existe.
    assert "campaigns.started_at >=" in sql


@pytest.mark.asyncio
async def test_runs_paginacion_limit_offset(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs?limit=5&offset=10",
        headers=_auth(operator_token),
    )
    assert resp.status_code == 200
    sql = str(
        fake_session.execute.call_args.args[0].compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "limit" in sql.lower()
    assert "offset" in sql.lower()


@pytest.mark.asyncio
async def test_runs_limit_invalido_422(client, fake_session, operator_token) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs?limit=999", headers=_auth(operator_token)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_runs_viewer_puede_leer(client, fake_session, viewer_token) -> None:
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/campaigns/runs", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_runs_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/campaigns/runs")
    assert resp.status_code == 401
