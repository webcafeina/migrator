"""Tests del endpoint GET /api/v1/campaigns/runs/{task_id}.

Mockeamos `AsyncResult` para simular todos los estados de Celery: PENDING,
STARTED, FAILURE y SUCCESS (con outputs vacíos, con outputs poblados, y
con un payload `{"status": "error"}` del propio agent).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import LeadStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _async_result(*, state: str, result=None, ready: bool | None = None) -> MagicMock:
    """Construye un MagicMock que imita celery.result.AsyncResult."""
    r = MagicMock()
    r.state = state
    r.result = result
    r.ready.return_value = (state in {"SUCCESS", "FAILURE"}) if ready is None else ready
    return r


# ---------- estados intermedios ----------

@pytest.mark.asyncio
async def test_run_status_pending(client, operator_token) -> None:
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="PENDING"),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/some-task-id", headers=_auth(operator_token)
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "PENDING"
    assert body["ready"] is False
    assert body["prospect"] is None
    assert body["pipeline"] is None
    assert body["error"] is None


@pytest.mark.asyncio
async def test_run_status_started(client, operator_token) -> None:
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="STARTED"),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/task-x", headers=_auth(operator_token)
        )
    assert resp.json()["state"] == "STARTED"
    assert resp.json()["prospect"] is None


@pytest.mark.asyncio
async def test_run_status_failure_exposes_error(client, operator_token) -> None:
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="FAILURE", result=Exception("boom")),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/task-x", headers=_auth(operator_token)
        )
    body = resp.json()
    assert body["state"] == "FAILURE"
    assert body["error"] == "boom"


# ---------- SUCCESS ----------

@pytest.mark.asyncio
async def test_run_status_success_without_leads(client, fake_session, operator_token) -> None:
    """Campaña que terminó sin crear leads (ej. Google devolvió 0 places)."""
    success_payload = {
        "status": "ok",
        "summary": "empty",
        "outputs": {
            "query": "x en y",
            "discovered": 0,
            "created": 0,
            "created_lead_ids": [],
            "skipped_duplicate": 0,
            "skipped_no_website": 0,
            "skipped_excluded": 0,
            "skipped_blocked_type": 0,
        },
        "warnings": ["Quota Google alcanzada"],
    }
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="SUCCESS", result=success_payload),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/task-x", headers=_auth(operator_token)
        )
    body = resp.json()
    assert body["state"] == "SUCCESS"
    assert body["ready"] is True
    assert body["prospect"]["created"] == 0
    assert body["prospect"]["warnings"] == ["Quota Google alcanzada"]
    assert body["pipeline"] == {"total": 0, "by_status": {}, "lead_ids": []}


@pytest.mark.asyncio
async def test_run_status_success_with_leads_querys_db(client, fake_session, operator_token) -> None:
    """Si la task creó leads, devuelve agregado by_status leído de BD."""
    success_payload = {
        "status": "ok",
        "summary": "ok",
        "outputs": {
            "query": "restauración en Madrid",
            "discovered": 5,
            "created": 3,
            "created_lead_ids": [10, 11, 12],
            "skipped_duplicate": 1,
            "skipped_no_website": 1,
            "skipped_excluded": 0,
            "skipped_blocked_type": 0,
        },
        "warnings": [],
    }
    # session.execute(select(status, count) group_by status) → 3 rows: 1 disc, 1 fingerprinted, 1 enriched
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (LeadStatus.DISCOVERED, 1),
        (LeadStatus.FINGERPRINTED, 1),
        (LeadStatus.ENRICHED, 1),
    ]

    async def _execute_async(_stmt):
        return rows_result

    fake_session.execute = MagicMock(side_effect=_execute_async)

    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="SUCCESS", result=success_payload),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/task-x", headers=_auth(operator_token)
        )
    body = resp.json()
    assert body["prospect"]["created"] == 3
    assert body["prospect"]["query"] == "restauración en Madrid"
    assert body["pipeline"]["total"] == 3
    assert body["pipeline"]["lead_ids"] == [10, 11, 12]
    assert body["pipeline"]["by_status"] == {
        "discovered": 1,
        "fingerprinted": 1,
        "enriched": 1,
    }


@pytest.mark.asyncio
async def test_run_status_success_but_agent_returned_error(client, operator_token) -> None:
    """ProspectorAgent capturó un GooglePlacesError → payload status=error."""
    error_payload = {"status": "error", "error": "Google Places falló: API key inválida"}
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="SUCCESS", result=error_payload),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/task-x", headers=_auth(operator_token)
        )
    body = resp.json()
    assert body["state"] == "SUCCESS"  # Celery dice SUCCESS, pero el agent reportó error
    assert "API key" in body["error"]
    assert body["prospect"] is None


# ---------- auth ----------

@pytest.mark.asyncio
async def test_run_status_no_auth_401(client) -> None:
    resp = await client.get("/api/v1/campaigns/runs/anything")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_status_viewer_ok(client, viewer_token) -> None:
    with patch(
        "wcm_api.routers.campaigns.AsyncResult",
        return_value=_async_result(state="PENDING"),
    ):
        resp = await client.get(
            "/api/v1/campaigns/runs/x", headers=_auth(viewer_token)
        )
    assert resp.status_code == 200
