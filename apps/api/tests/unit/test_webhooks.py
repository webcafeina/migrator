"""Tests del webhook /api/v1/webhooks/clickup (HMAC signature)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import MagicMock

import pytest


def _hmac_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_no_secret_returns_unauthorized(client) -> None:
    # CLICKUP_WEBHOOK_SECRET no está en el env de tests por defecto
    response = await client.post(
        "/api/v1/webhooks/clickup", content=b"{}", headers={"X-Signature": "x"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(monkeypatch, client) -> None:
    monkeypatch.setenv("CLICKUP_WEBHOOK_SECRET", "supersecret")
    # Limpiar la cache del settings para que recoja el cambio
    from wcm_api.config import get_settings
    get_settings.cache_clear()

    body = b'{"event":"taskStatusUpdated"}'
    response = await client.post(
        "/api/v1/webhooks/clickup",
        content=body,
        headers={"X-Signature": "wrong_hash"},
    )
    assert response.status_code == 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_webhook_valid_signature_processed(monkeypatch, client, fake_session) -> None:
    monkeypatch.setenv("CLICKUP_WEBHOOK_SECRET", "supersecret")
    from wcm_api.config import get_settings
    get_settings.cache_clear()

    body = json.dumps({
        "event": "taskStatusUpdated",
        "task_id": "abc123",
        "status": {"status": "complete"},
    }).encode()

    sig = _hmac_signature(body, "supersecret")

    # No hay residual con clickup_task_id=abc123 → debe completar sin error
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session.execute.return_value = result

    response = await client.post(
        "/api/v1/webhooks/clickup",
        content=body,
        headers={"X-Signature": sig, "content-type": "application/json"},
    )
    assert response.status_code == 204

    get_settings.cache_clear()
