"""Tests de endpoints añadidos en Fase 10:
- POST /api/v1/outreach/sequences/{id}/send
- POST /webhooks/resend
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import (
    OutreachSendStatus,
    OutreachSequenceStatus,
)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- /outreach/sequences/{id}/send ----------

@pytest.mark.asyncio
async def test_send_404_when_sequence_missing(client, fake_session, operator_token) -> None:
    fake_session.get.return_value = None
    resp = await client.post(
        "/api/v1/outreach/sequences/99/send",
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_409_when_sequence_not_ready(client, fake_session, operator_token) -> None:
    seq = MagicMock()
    seq.status = OutreachSequenceStatus.DRAFT_PENDING_REVIEW
    fake_session.get.return_value = seq
    resp = await client.post(
        "/api/v1/outreach/sequences/1/send",
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_send_409_when_no_queued_step(client, fake_session, operator_token) -> None:
    seq = MagicMock()
    seq.status = OutreachSequenceStatus.READY
    fake_session.get.return_value = seq
    scalars = MagicMock()
    scalars.first.return_value = None
    res = MagicMock()
    res.scalars.return_value = scalars
    fake_session.execute.return_value = res

    resp = await client.post(
        "/api/v1/outreach/sequences/1/send",
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_send_queues_celery_task(client, fake_session, operator_token) -> None:
    seq = MagicMock()
    seq.status = OutreachSequenceStatus.READY
    send = MagicMock()
    send.id = 55
    send.step_index = 0
    fake_session.get.return_value = seq
    scalars = MagicMock()
    scalars.first.return_value = send
    res = MagicMock()
    res.scalars.return_value = scalars
    fake_session.execute.return_value = res

    with patch(
        "wcm_api.routers.outreach.enqueue_outreach_send",
        return_value="celery-task-1",
    ) as mock_enq:
        resp = await client.post(
            "/api/v1/outreach/sequences/1/send",
            headers=auth_headers(operator_token),
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["send_id"] == 55
    assert body["task_id"] == "celery-task-1"
    mock_enq.assert_called_once_with(55)


# ---------- /webhooks/resend ----------

def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_resend_webhook_401_without_secret_configured(client) -> None:
    body = json.dumps({"type": "email.delivered", "data": {"email_id": "x"}}).encode()
    resp = await client.post(
        "/api/v1/webhooks/resend", content=body,
        headers={"Content-Type": "application/json", "svix-signature": "anything"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_resend_webhook_401_invalid_signature(client, monkeypatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "topsecret")
    from wcm_api.config import get_settings
    get_settings.cache_clear()
    try:
        body = json.dumps({"type": "email.delivered", "data": {"email_id": "x"}}).encode()
        resp = await client.post(
            "/api/v1/webhooks/resend", content=body,
            headers={"Content-Type": "application/json", "svix-signature": "bad"},
        )
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resend_webhook_updates_send_on_open(client, fake_session, monkeypatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "topsecret")
    from wcm_api.config import get_settings
    get_settings.cache_clear()
    try:
        body = json.dumps({
            "type": "email.opened",
            "data": {"email_id": "msg-1"},
        }).encode()
        signature = _sign("topsecret", body)

        send = MagicMock()
        send.id = 9
        send.status = OutreachSendStatus.SENT
        send.opened_at = None
        scalars_result = MagicMock()
        scalars_result.scalar_one_or_none.return_value = send
        fake_session.execute.return_value = scalars_result

        resp = await client.post(
            "/api/v1/webhooks/resend",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-signature": f"v1,{signature}",
            },
        )
        assert resp.status_code == 204
        assert send.status == OutreachSendStatus.OPENED
        assert send.opened_at is not None
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resend_webhook_no_match_returns_204(client, fake_session, monkeypatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "topsecret")
    from wcm_api.config import get_settings
    get_settings.cache_clear()
    try:
        body = json.dumps({"type": "email.bounced", "data": {"email_id": "unknown"}}).encode()
        signature = _sign("topsecret", body)

        scalars_result = MagicMock()
        scalars_result.scalar_one_or_none.return_value = None
        fake_session.execute.return_value = scalars_result

        resp = await client.post(
            "/api/v1/webhooks/resend",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-signature": signature,
            },
        )
        assert resp.status_code == 204
    finally:
        get_settings.cache_clear()
