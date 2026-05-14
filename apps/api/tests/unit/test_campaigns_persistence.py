"""Tests de:
- POST /api/v1/campaigns/launch persiste Campaign(status=queued).
- GET /api/v1/campaigns/active devuelve solo campañas queued/running.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import CampaignStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _campaign(
    *, id_: int = 1, status: CampaignStatus = CampaignStatus.QUEUED,
    sector: str = "x", region: str = "y", task_id: str = "task-1",
    target: int = 5, lead_ids: list[int] | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = id_
    c.task_id = task_id
    c.sector = sector
    c.region = region
    c.target_count = target
    c.status = status
    c.started_at = None
    c.created_lead_ids = lead_ids or []
    return c


# ---------- POST /campaigns/launch ----------

@pytest.mark.asyncio
async def test_launch_creates_campaign_row(client, fake_session, operator_token) -> None:
    """POST /launch encola task y persiste Campaign(status=queued)."""
    fake_session.refresh.side_effect = lambda c: setattr(c, "id", 42)

    with patch("wcm_api.routers.campaigns.enqueue_prospect_campaign", return_value="task-xyz") as enq:
        resp = await client.post(
            "/api/v1/campaigns/launch",
            json={"sector": "bar", "region": "Madrid", "target_count": 5},
            headers=_auth(operator_token),
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-xyz"
    assert body["campaign_id"] == 42
    assert body["status"] == "queued"
    enq.assert_called_once()

    # Verificar que se llamó a session.add con un Campaign correctamente formado
    added = fake_session.add.call_args.args[0]
    assert added.task_id == "task-xyz"
    assert added.sector == "bar"
    assert added.region == "Madrid"
    assert added.target_count == 5
    assert added.status == CampaignStatus.QUEUED


@pytest.mark.asyncio
async def test_launch_requires_operator(client, fake_session, viewer_token) -> None:
    resp = await client.post(
        "/api/v1/campaigns/launch",
        json={"sector": "x", "region": "y", "target_count": 5},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403


# ---------- GET /campaigns/active ----------

@pytest.mark.asyncio
async def test_active_returns_running_campaigns(client, fake_session, operator_token) -> None:
    """/active devuelve solo campañas no terminadas, ordenadas DESC."""
    rows = [
        _campaign(id_=2, status=CampaignStatus.RUNNING, sector="restaurante", region="Sevilla"),
        _campaign(id_=1, status=CampaignStatus.QUEUED, sector="bar", region="Cáceres"),
    ]
    scalars = MagicMock()
    scalars.all.return_value = rows
    result = MagicMock()
    result.scalars.return_value = scalars
    fake_session.execute.return_value = result

    resp = await client.get("/api/v1/campaigns/active", headers=_auth(operator_token))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["id"] == 2
    assert body[0]["status"] == "running"
    assert body[0]["sector"] == "restaurante"
    assert body[1]["status"] == "queued"


@pytest.mark.asyncio
async def test_active_empty_when_none_running(client, fake_session, operator_token) -> None:
    scalars = MagicMock()
    scalars.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars
    fake_session.execute.return_value = result

    resp = await client.get("/api/v1/campaigns/active", headers=_auth(operator_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_active_viewer_ok(client, fake_session, viewer_token) -> None:
    """Cualquier rol autenticado (incluido viewer) puede ver el indicador."""
    scalars = MagicMock()
    scalars.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars
    fake_session.execute.return_value = result

    resp = await client.get("/api/v1/campaigns/active", headers=_auth(viewer_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_active_no_auth_401(client) -> None:
    resp = await client.get("/api/v1/campaigns/active")
    assert resp.status_code == 401
