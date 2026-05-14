"""Tests del ResendNotifierAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.resend_notifier import ResendNotifierAgent
from wcm_worker.errors import ResendNotifierError
from wcm_worker.integrations.resend import ResendSendResult


def _ctx(fake_session, **overrides) -> AgentContext:
    extra = {
        "recipients": ["ops@webcafeina.com"],
        "subject": "Resumen",
        "body_text": "Hola",
    }
    extra.update(overrides)
    return AgentContext(session=fake_session, extra=extra)


def test_notifier_requires_recipients(fake_session) -> None:
    with pytest.raises(ResendNotifierError):
        ResendNotifierAgent().run(
            AgentContext(session=fake_session, extra={"subject": "x", "body_text": "y"})
        )


def test_notifier_rejects_external_email(fake_session) -> None:
    with pytest.raises(ResendNotifierError, match="interno"):
        ResendNotifierAgent().run(_ctx(fake_session, recipients=["someone@gmail.com"]))


def test_notifier_skipped_without_resend_key(fake_session, monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    result = ResendNotifierAgent().run(_ctx(fake_session))
    assert result.outputs["skipped"] is True
    assert "ops@webcafeina.com" in result.outputs["would_send_to"]


def test_notifier_sends_via_client(fake_session) -> None:
    fake_client = MagicMock()
    fake_client.send.return_value = ResendSendResult(message_id="m-1")
    agent = ResendNotifierAgent(client=fake_client)
    result = agent.run(_ctx(fake_session))
    assert result.outputs["message_id"] == "m-1"
    fake_client.send.assert_called_once()
    args = fake_client.send.call_args.kwargs
    assert args["to"] == ["ops@webcafeina.com"]
    assert args["subject"] == "Resumen"
