"""Tests de los endpoints de leads añadidos en Fase 9:
- POST /api/v1/leads/{id}/opt-out-url
- POST /api/v1/leads/{id}/consent
- POST /api/v1/leads/{id}/outreach/compose
- GET/POST /api/v1/outreach/sequences

Foco: contratos y validaciones, no integración con worker real.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_types.enums import LeadStatus, OutreachSequenceStatus


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _lead_obj(*, lead_id: int = 1, emails: list[str] | None = None) -> MagicMock:
    lead = MagicMock()
    lead.id = lead_id
    lead.url = "https://barpepe.es"
    lead.business_name = "Bar Pepe"
    lead.emails = emails if emails is not None else ["hola@barpepe.es"]
    lead.status = LeadStatus.ENRICHED
    return lead


# ---------- /opt-out-url ----------

@pytest.mark.asyncio
async def test_opt_out_url_requires_operator(client, viewer_token) -> None:
    resp = await client.post(
        "/api/v1/leads/1/opt-out-url", headers=auth_headers(viewer_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_opt_out_url_404_when_lead_missing(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = None
    resp = await client.post(
        "/api/v1/leads/999/opt-out-url", headers=auth_headers(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_opt_out_url_409_when_no_email(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead_obj(emails=[])
    resp = await client.post(
        "/api/v1/leads/1/opt-out-url", headers=auth_headers(operator_token)
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_opt_out_url_returns_signed_url(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead_obj()
    resp = await client.post(
        "/api/v1/leads/1/opt-out-url", headers=auth_headers(operator_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lead_id"] == 1
    assert body["email"] == "hola@barpepe.es"
    assert body["url"].startswith("http")
    assert "token=" in body["url"]


# ---------- /consent ----------

@pytest.mark.asyncio
async def test_consent_objection_marks_opted_out(client, fake_session, operator_token) -> None:
    lead = _lead_obj()
    fake_session.get.return_value = lead

    resp = await client.post(
        "/api/v1/leads/1/consent",
        json={"action": "objection_received", "note": "Llamó pidiendo baja"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["action"] == "objection_received"
    assert body["new_status"] == LeadStatus.OPTED_OUT.value
    fake_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_consent_manual_review_changes_status(client, fake_session, operator_token) -> None:
    lead = _lead_obj()
    fake_session.get.return_value = lead

    resp = await client.post(
        "/api/v1/leads/1/consent",
        json={"action": "manual_review"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 201
    assert resp.json()["new_status"] == LeadStatus.MANUAL_REVIEW.value


@pytest.mark.asyncio
async def test_consent_invalid_action_422(client, fake_session, operator_token) -> None:
    resp = await client.post(
        "/api/v1/leads/1/consent",
        json={"action": "nuke_everything"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 422


# ---------- /outreach/compose ----------

@pytest.mark.asyncio
async def test_outreach_compose_queues_celery(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead_obj()

    with patch(
        "wcm_api.routers.leads.enqueue_outreach_compose", return_value="task-uuid-1"
    ) as mock_enqueue:
        resp = await client.post(
            "/api/v1/leads/1/outreach/compose",
            headers=auth_headers(operator_token),
        )

    assert resp.status_code == 202
    assert resp.json()["task_id"] == "task-uuid-1"
    mock_enqueue.assert_called_once()
    args, kwargs = mock_enqueue.call_args
    assert args[0] == 1
    assert "opt_out_token" in kwargs


@pytest.mark.asyncio
async def test_outreach_compose_409_when_no_email(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = _lead_obj(emails=[])
    resp = await client.post(
        "/api/v1/leads/1/outreach/compose",
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 409


# ---------- /outreach/sequences ----------

@pytest.mark.asyncio
async def test_list_sequences_filters_by_status(client, fake_session, viewer_token) -> None:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []  # no rows
    res_mock = MagicMock()
    res_mock.scalars.return_value = scalars_mock
    fake_session.execute.return_value = res_mock

    resp = await client.get(
        "/api/v1/outreach/sequences?status=draft_pending_review&limit=10",
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_transition_invalid_from_state_409(client, fake_session, operator_token) -> None:
    seq = MagicMock()
    seq.id = 1
    seq.status = OutreachSequenceStatus.COMPLETED  # estado final, no se puede transicionar
    seq.legal_validation_passed = True
    fake_session.get.return_value = seq

    resp = await client.post(
        "/api/v1/outreach/sequences/1/transition",
        json={"action": "approve"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_transition_approve_without_legal_validation_blocked(
    client, fake_session, operator_token
) -> None:
    seq = MagicMock()
    seq.id = 1
    seq.status = OutreachSequenceStatus.DRAFT_PENDING_REVIEW
    seq.legal_validation_passed = False
    fake_session.get.return_value = seq

    resp = await client.post(
        "/api/v1/outreach/sequences/1/transition",
        json={"action": "approve"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 409
    assert "validación legal" in resp.json()["error"]["message"].lower()
