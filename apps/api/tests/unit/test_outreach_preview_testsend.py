"""Tests preview HTML del step + test-send (v0.14.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _send_mock(
    *,
    body_html_rendered: str | None = "<p>HTML snapshot</p>",
    body_rendered: str = "Texto plano",
    subject: str = "Hola",
) -> MagicMock:
    m = MagicMock()
    m.id = 11
    m.sequence_id = 7
    m.step_index = 0
    m.subject = subject
    m.body_rendered = body_rendered
    m.body_html_rendered = body_html_rendered
    return m


def _execute_returning(send) -> AsyncMock:
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=send)
    return AsyncMock(return_value=res)


# --- preview ---


@pytest.mark.asyncio
async def test_preview_step_devuelve_snapshot_html_si_existe(
    client, fake_session, viewer_token
) -> None:
    send = _send_mock(body_html_rendered="<html><body>Snapshot Bar Pepe</body></html>")
    fake_session.execute = _execute_returning(send)

    resp = await client.get(
        "/api/v1/outreach/sequences/7/steps/0/preview",
        headers=_auth(viewer_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "Snapshot Bar Pepe" in body["html"]
    assert body["subject"] == "Hola"


@pytest.mark.asyncio
async def test_preview_step_regenera_html_para_send_legacy(
    client, fake_session, viewer_token
) -> None:
    """Sends pre-v0.14.0 con body_html_rendered NULL → regen on-the-fly."""
    send = _send_mock(body_html_rendered=None, body_rendered="Hola legacy.\n\nLine 2.")
    fake_session.execute = _execute_returning(send)
    # session.get (EmailLayout, 1) → None → fallback hardcoded
    fake_session.get = AsyncMock(return_value=None)

    resp = await client.get(
        "/api/v1/outreach/sequences/7/steps/0/preview",
        headers=_auth(viewer_token),
    )

    assert resp.status_code == 200
    html = resp.json()["html"]
    # Premailer añade atributos style a los <p>; busco solo el texto.
    assert "Hola legacy." in html
    assert "Line 2." in html
    # Y la apertura del wrap <p> aunque tenga style.
    assert html.count("<p") >= 2


@pytest.mark.asyncio
async def test_preview_step_404_si_step_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.execute = _execute_returning(None)
    resp = await client.get(
        "/api/v1/outreach/sequences/7/steps/0/preview",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 404


# --- test-send ---


@pytest.mark.asyncio
async def test_test_send_requires_operator(client, fake_session, viewer_token) -> None:
    """Viewer no puede disparar envío de prueba (consume créditos Resend)."""
    resp = await client.post(
        "/api/v1/outreach/sequences/7/steps/0/test-send",
        headers=_auth(viewer_token),
        json={"to": "test@webcafeina.com"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_test_send_email_invalido_422(client, fake_session, operator_token) -> None:
    resp = await client.post(
        "/api/v1/outreach/sequences/7/steps/0/test-send",
        headers=_auth(operator_token),
        json={"to": "no-es-email"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_test_send_sin_resend_key_503(
    client, fake_session, operator_token, monkeypatch
) -> None:
    """RESEND_API_KEY ausente → 503 explicativo."""
    send = _send_mock()
    fake_session.execute = _execute_returning(send)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    resp = await client.post(
        "/api/v1/outreach/sequences/7/steps/0/test-send",
        headers=_auth(operator_token),
        json={"to": "test@webcafeina.com"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_test_send_happy_path_audita_y_devuelve_message_id(
    client, fake_session, operator_token, monkeypatch
) -> None:
    send = _send_mock()
    fake_session.execute = _execute_returning(send)
    monkeypatch.setenv("RESEND_API_KEY", "test-key")

    # Mock del ResendClient para no llamar a Resend de verdad.
    from wcm_worker.integrations.resend import ResendSendResult

    fake_client = MagicMock()
    fake_client.send.return_value = ResendSendResult(message_id="re_test")

    class FakeClientFactory:
        @staticmethod
        def from_env():
            return fake_client

    monkeypatch.setattr("wcm_worker.integrations.resend.ResendClient", FakeClientFactory)

    resp = await client.post(
        "/api/v1/outreach/sequences/7/steps/0/test-send",
        headers=_auth(operator_token),
        json={"to": "test@webcafeina.com"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_message_id"] == "re_test"
    assert body["to"] == "test@webcafeina.com"

    # Resend recibió subject con prefijo [PRUEBA] + html snapshot.
    call = fake_client.send.call_args
    assert call.kwargs["subject"].startswith("[PRUEBA]")
    assert call.kwargs["body_html"] == "<p>HTML snapshot</p>"
    assert call.kwargs["to"] == ["test@webcafeina.com"]

    # AuditLog TEST_SEND escrito.
    audit_added = [
        c.args[0] for c in fake_session.add.call_args_list if type(c.args[0]).__name__ == "AuditLog"
    ]
    assert len(audit_added) == 1
    assert audit_added[0].action.value == "test_send"
    assert audit_added[0].payload["to"] == "test@webcafeina.com"


@pytest.mark.asyncio
async def test_test_send_resend_falla_502(
    client, fake_session, operator_token, monkeypatch
) -> None:
    """Resend rechaza → 502 con mensaje del proveedor (no toca status)."""
    send = _send_mock()
    fake_session.execute = _execute_returning(send)
    monkeypatch.setenv("RESEND_API_KEY", "test-key")

    from wcm_worker.integrations.resend import ResendApiError

    fake_client = MagicMock()
    fake_client.send.side_effect = ResendApiError("Domain not verified")

    class FakeClientFactory:
        @staticmethod
        def from_env():
            return fake_client

    monkeypatch.setattr("wcm_worker.integrations.resend.ResendClient", FakeClientFactory)

    resp = await client.post(
        "/api/v1/outreach/sequences/7/steps/0/test-send",
        headers=_auth(operator_token),
        json={"to": "test@webcafeina.com"},
    )
    assert resp.status_code == 502
    assert "Domain not verified" in resp.json()["detail"]
    # No se persiste AuditLog ni se muta nada.
    fake_session.commit.assert_not_called()
