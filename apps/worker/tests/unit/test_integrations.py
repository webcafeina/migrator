"""Tests de los clientes de integración (sin red real)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from wcm_worker.integrations.clickup import ClickupApiError, ClickupClient
from wcm_worker.integrations.r2 import R2Client, R2UploadError
from wcm_worker.integrations.resend import (
    ResendApiError,
    ResendClient,
    ResendSendResult,
)

# ---------- ClickupClient ----------

class _MockTransport(httpx.MockTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)
        super().__init__(lambda req: next(self._responses))


def _clickup(http: httpx.Client) -> ClickupClient:
    return ClickupClient(
        api_token="pk_test", http_client=http, retry_base_delay_s=0.001,
        default_list_id="123",
    )


def test_clickup_rejects_empty_token() -> None:
    with pytest.raises(ClickupApiError):
        ClickupClient(api_token="")


def test_clickup_from_env_returns_none_without_token(monkeypatch) -> None:
    monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
    assert ClickupClient.from_env() is None


def test_clickup_create_task_returns_payload() -> None:
    http = httpx.Client(transport=_MockTransport([
        httpx.Response(200, json={"id": "abc123", "name": "task"}),
    ]))
    client = _clickup(http)
    result = client.create_task(title="task", description="d", priority=2)
    assert result["id"] == "abc123"


def test_clickup_create_task_requires_list_id() -> None:
    http = httpx.Client(transport=_MockTransport([httpx.Response(200, json={})]))
    client = ClickupClient(api_token="pk", default_list_id=None, http_client=http,
                           retry_base_delay_s=0.001)
    with pytest.raises(ClickupApiError, match="list_id"):
        client.create_task(title="x")


def test_clickup_retries_5xx_then_raises() -> None:
    http = httpx.Client(transport=_MockTransport([
        httpx.Response(503, text="x"),
        httpx.Response(503, text="x"),
        httpx.Response(503, text="x"),
    ]))
    client = _clickup(http)
    with pytest.raises(ClickupApiError) as exc:
        client.create_task(title="x")
    assert exc.value.status_code == 503


def test_clickup_no_retry_on_4xx() -> None:
    http = httpx.Client(transport=_MockTransport([
        httpx.Response(400, text="bad payload"),
    ]))
    client = _clickup(http)
    with pytest.raises(ClickupApiError) as exc:
        client.create_task(title="x")
    assert exc.value.status_code == 400


def test_clickup_find_member_returns_user_id() -> None:
    http = httpx.Client(transport=_MockTransport([
        httpx.Response(200, json={"members": [
            {"user": {"id": 11111111, "username": "operador", "email": "ops@webcafeina.com"}}
        ]}),
    ]))
    client = ClickupClient(api_token="pk", team_id="20483773", http_client=http,
                           retry_base_delay_s=0.001)
    assert client.find_member("operador") == 11111111


# ---------- ResendClient ----------

def test_resend_from_env_returns_none_without_key(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert ResendClient.from_env() is None


def test_resend_send_returns_message_id() -> None:
    sdk = MagicMock()
    sdk.Emails.send = MagicMock(return_value={"id": "msg-abc"})
    client = ResendClient(api_key="key", sdk_module=sdk)
    result = client.send(to=["x@webcafeina.com"], subject="s", body_text="b")
    assert isinstance(result, ResendSendResult)
    assert result.message_id == "msg-abc"
    sdk.Emails.send.assert_called_once()


def test_resend_send_retries_on_exception() -> None:
    sdk = MagicMock()
    sdk.Emails.send.side_effect = [RuntimeError("net"), {"id": "ok"}]
    client = ResendClient(api_key="key", sdk_module=sdk, max_retries=3,
                          retry_base_delay_s=0.001)
    result = client.send(to=["a@webcafeina.com"], subject="s", body_text="b")
    assert result.message_id == "ok"
    assert sdk.Emails.send.call_count == 2


def test_resend_send_raises_after_max_retries() -> None:
    sdk = MagicMock()
    sdk.Emails.send.side_effect = RuntimeError("persistent")
    client = ResendClient(api_key="key", sdk_module=sdk, max_retries=2,
                          retry_base_delay_s=0.001)
    with pytest.raises(ResendApiError, match="2 intentos"):
        client.send(to=["a@webcafeina.com"], subject="s", body_text="b")


def test_resend_send_requires_recipients() -> None:
    client = ResendClient(api_key="key", sdk_module=MagicMock())
    with pytest.raises(ResendApiError, match="destinatarios"):
        client.send(to=[], subject="s", body_text="b")


def test_resend_verify_webhook_signature_ok() -> None:
    import hashlib
    import hmac
    client = ResendClient(api_key="key", webhook_secret="topsecret",
                          sdk_module=MagicMock())
    body = b'{"foo":"bar"}'
    sig = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert client.verify_webhook_signature(body, sig) is True
    assert client.verify_webhook_signature(body, "nope") is False
    assert client.verify_webhook_signature(body, None) is False


def test_resend_verify_signature_returns_false_without_secret() -> None:
    client = ResendClient(api_key="key", sdk_module=MagicMock())
    assert client.verify_webhook_signature(b"x", "sig") is False


# ---------- R2Client ----------

def test_r2_from_env_returns_none_without_creds(monkeypatch) -> None:
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    assert R2Client.from_env() is None


def test_r2_put_bytes_returns_public_url() -> None:
    s3 = MagicMock()
    client = R2Client(
        account_id="acc", access_key_id="k", secret_access_key="s",
        bucket="b", public_url_base="https://cdn.webcafeina.com",
        s3_client=s3,
    )
    url = client.put_bytes("x/y.webp", b"data", content_type="image/webp")
    assert url == "https://cdn.webcafeina.com/x/y.webp"
    s3.put_object.assert_called_once()


def test_r2_put_bytes_no_public_base_returns_s3_uri() -> None:
    s3 = MagicMock()
    client = R2Client(
        account_id="acc", access_key_id="k", secret_access_key="s",
        bucket="bk", s3_client=s3,
    )
    url = client.put_bytes("a.bin", b"d")
    assert url == "s3://bk/a.bin"


def test_r2_put_bytes_raises_on_s3_error() -> None:
    s3 = MagicMock()
    s3.put_object.side_effect = RuntimeError("boom")
    client = R2Client(
        account_id="acc", access_key_id="k", secret_access_key="s",
        bucket="bk", s3_client=s3,
    )
    with pytest.raises(R2UploadError):
        client.put_bytes("x.bin", b"d")


def test_r2_head_object_returns_none_on_404() -> None:
    s3 = MagicMock()
    s3.head_object.side_effect = RuntimeError("404 Not Found")
    client = R2Client(
        account_id="acc", access_key_id="k", secret_access_key="s",
        bucket="bk", s3_client=s3,
    )
    assert client.head_object("missing") is None
