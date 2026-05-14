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
    """POST /launch persiste Campaign(status=queued) ANTES de encolar y
    genera el task_id en el API (no en Celery) para evitar race condition
    con el worker.
    """
    fake_session.refresh.side_effect = lambda c: setattr(c, "id", 42)

    with patch("wcm_api.routers.campaigns.enqueue_prospect_campaign", return_value="ignored") as enq:
        resp = await client.post(
            "/api/v1/campaigns/launch",
            json={"sector": "bar", "region": "Madrid", "target_count": 5},
            headers=_auth(operator_token),
        )
    assert resp.status_code == 202
    body = resp.json()
    # task_id es UUID v4 generado por el endpoint
    assert len(body["task_id"]) == 36
    assert body["task_id"].count("-") == 4
    assert body["campaign_id"] == 42
    assert body["status"] == "queued"

    # El task_id se pasa a enqueue como kwarg (orden: commit primero, encolar después).
    enq.assert_called_once()
    assert enq.call_args.kwargs.get("task_id") == body["task_id"]

    # Y la Campaign persistida lleva el mismo task_id.
    added = fake_session.add.call_args.args[0]
    assert added.task_id == body["task_id"]
    assert added.sector == "bar"
    assert added.region == "Madrid"
    assert added.target_count == 5
    assert added.status == CampaignStatus.QUEUED


@pytest.mark.asyncio
async def test_launch_commits_before_enqueue(client, fake_session, operator_token) -> None:
    """Regresión del race condition: la Campaign debe estar committed
    ANTES de encolar la task. Si no, el worker puede ejecutarse antes de
    que la fila esté en BD y `_find_campaign_by_task_id` devolverá None
    → Campaign atascada en QUEUED.

    Verificamos que cuando enqueue es invocado, fake_session.commit YA
    se llamó al menos una vez (snapshot del await_count al momento de
    enqueue vs al final del request).
    """
    fake_session.refresh.side_effect = lambda c: setattr(c, "id", 1)

    commits_when_enqueued: list[int] = []

    def _enqueue_side_effect(*a, **kw):
        commits_when_enqueued.append(fake_session.commit.await_count)
        return "any"

    with patch("wcm_api.routers.campaigns.enqueue_prospect_campaign", side_effect=_enqueue_side_effect):
        resp = await client.post(
            "/api/v1/campaigns/launch",
            json={"sector": "bar", "region": "Madrid", "target_count": 5},
            headers=_auth(operator_token),
        )

    assert resp.status_code == 202
    assert commits_when_enqueued, "enqueue nunca se llamó"
    assert commits_when_enqueued[0] >= 1, (
        f"commit debe haber corrido antes de enqueue, await_count={commits_when_enqueued[0]}"
    )


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
