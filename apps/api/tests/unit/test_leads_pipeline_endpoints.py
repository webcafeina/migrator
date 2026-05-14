"""Tests de POST /api/v1/leads/{id}/enrich y /refingerprint (WCM-027).

Cubrimos: contrato (202 + task_id), 404 si no existe, 403 si rol viewer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import LeadStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _lead(lead_id: int = 1) -> MagicMock:
    lead = MagicMock()
    lead.id = lead_id
    lead.url = "https://x.com"
    lead.status = LeadStatus.DISCOVERED
    return lead


# ---------- POST /leads/{id}/enrich ----------

@pytest.mark.asyncio
async def test_enrich_endpoint_encola_y_devuelve_task_id(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead(42)
    with patch("wcm_api.routers.leads.enqueue_lead_enrich", return_value="task-abc") as enq:
        resp = await client.post(
            "/api/v1/leads/42/enrich", headers=_auth(operator_token)
        )
    assert resp.status_code == 202
    assert resp.json() == {"task_id": "task-abc", "status": "queued"}
    enq.assert_called_once_with(42, skip_embedding=False)


@pytest.mark.asyncio
async def test_enrich_endpoint_skip_embedding_query(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead(42)
    with patch("wcm_api.routers.leads.enqueue_lead_enrich", return_value="task-x") as enq:
        resp = await client.post(
            "/api/v1/leads/42/enrich?skip_embedding=true",
            headers=_auth(operator_token),
        )
    assert resp.status_code == 202
    enq.assert_called_once_with(42, skip_embedding=True)


@pytest.mark.asyncio
async def test_enrich_endpoint_404_si_lead_no_existe(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = None
    resp = await client.post(
        "/api/v1/leads/999/enrich", headers=_auth(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_enrich_endpoint_viewer_403(client, fake_session, viewer_token) -> None:
    fake_session.get.return_value = _lead(1)
    resp = await client.post(
        "/api/v1/leads/1/enrich", headers=_auth(viewer_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_enrich_endpoint_sin_token_401(client) -> None:
    resp = await client.post("/api/v1/leads/1/enrich")
    assert resp.status_code == 401


# ---------- POST /leads/{id}/refingerprint (cobertura previa faltante) ----------

@pytest.mark.asyncio
async def test_refingerprint_endpoint_encola_y_devuelve_task_id(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead(7)
    with patch("wcm_api.routers.leads.enqueue_lead_fingerprint", return_value="task-fp") as enq:
        resp = await client.post(
            "/api/v1/leads/7/refingerprint", headers=_auth(operator_token)
        )
    assert resp.status_code == 202
    assert resp.json() == {"task_id": "task-fp", "status": "queued"}
    enq.assert_called_once_with(7)


@pytest.mark.asyncio
async def test_refingerprint_endpoint_404_si_lead_no_existe(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = None
    resp = await client.post(
        "/api/v1/leads/999/refingerprint", headers=_auth(operator_token)
    )
    assert resp.status_code == 404
