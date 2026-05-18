"""Tests del OutreachSenderAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_types.enums import (
    OutreachSendStatus,
    OutreachSequenceStatus,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.outreach_sender import OutreachSenderAgent
from wcm_worker.errors import OutreachSenderError
from wcm_worker.integrations.resend import ResendApiError, ResendSendResult


def _send_mock(
    *,
    status=OutreachSendStatus.QUEUED,
    body_html_rendered: str | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = 11
    m.sequence_id = 7
    m.lead_id = 99
    m.step_index = 0
    m.subject = "Hola"
    m.body_rendered = "Cuerpo"
    m.body_html_rendered = body_html_rendered
    m.status = status
    m.provider_message_id = None
    m.sent_at = None
    return m


def _seq_mock(*, status=OutreachSequenceStatus.READY) -> MagicMock:
    s = MagicMock()
    s.id = 7
    s.status = status
    return s


def _lead_mock(emails=None) -> MagicMock:
    l = MagicMock()
    l.id = 99
    l.emails = emails if emails is not None else ["x@example.com"]
    return l


def _ctx(fake_session, *, send_id=11) -> AgentContext:
    return AgentContext(
        session=fake_session,
        extra={"outreach_send_id": send_id},
    )


def _setup_session(fake_session, send, seq, lead, *, opted_email: str | None = None) -> None:
    fake_session.get.side_effect = lambda model, id_: {
        ("OutreachSend", 11): send,
        ("OutreachSequence", 7): seq,
        ("Lead", 99): lead,
    }.get((model.__name__, id_))
    res = MagicMock()
    res.first.return_value = (opted_email,) if opted_email else None
    fake_session.execute.return_value = res


def test_sender_requires_send_id(fake_session) -> None:
    with pytest.raises(OutreachSenderError):
        OutreachSenderAgent().run(AgentContext(session=fake_session))


def test_sender_send_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(OutreachSenderError, match="no encontrado"):
        OutreachSenderAgent().run(_ctx(fake_session))


def test_sender_rejects_non_queued_send(fake_session) -> None:
    send = _send_mock(status=OutreachSendStatus.SENT)
    seq = _seq_mock()
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)
    with pytest.raises(OutreachSenderError, match="QUEUED"):
        OutreachSenderAgent().run(_ctx(fake_session))


def test_sender_rejects_sequence_not_ready(fake_session) -> None:
    send = _send_mock()
    seq = _seq_mock(status=OutreachSequenceStatus.DRAFT_PENDING_REVIEW)
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)
    with pytest.raises(OutreachSenderError, match="READY"):
        OutreachSenderAgent().run(_ctx(fake_session))


def test_sender_aborts_when_lead_opted_out(fake_session) -> None:
    send = _send_mock()
    seq = _seq_mock()
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead, opted_email="x@example.com")

    fake_client = MagicMock()
    with pytest.raises(OutreachSenderError, match="opt_out_log"):
        OutreachSenderAgent(client=fake_client).run(_ctx(fake_session))
    assert send.status == OutreachSendStatus.FAILED
    fake_client.send.assert_not_called()


def test_sender_aborts_when_lead_has_no_email(fake_session) -> None:
    send = _send_mock()
    seq = _seq_mock()
    lead = _lead_mock(emails=[])
    _setup_session(fake_session, send, seq, lead)
    with pytest.raises(OutreachSenderError, match="sin email"):
        OutreachSenderAgent(client=MagicMock()).run(_ctx(fake_session))
    assert send.status == OutreachSendStatus.FAILED


def test_sender_skipped_without_resend_key(fake_session, monkeypatch) -> None:
    send = _send_mock()
    seq = _seq_mock()
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    result = OutreachSenderAgent().run(_ctx(fake_session))
    assert result.outputs == {"skipped": True}
    # Send sigue QUEUED — el operador puede reintentar cuando haya key.
    assert send.status == OutreachSendStatus.QUEUED


def test_sender_sends_and_persists_message_id(fake_session) -> None:
    send = _send_mock()
    seq = _seq_mock(status=OutreachSequenceStatus.READY)
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)

    fake_client = MagicMock()
    fake_client.send.return_value = ResendSendResult(message_id="re_xyz", status="queued")

    result = OutreachSenderAgent(client=fake_client).run(_ctx(fake_session))

    assert send.status == OutreachSendStatus.SENT
    assert send.provider_message_id == "re_xyz"
    assert send.sent_at is not None
    assert seq.status == OutreachSequenceStatus.IN_PROGRESS  # promoted
    assert result.outputs["message_id"] == "re_xyz"


def test_sender_failure_marks_send_failed(fake_session) -> None:
    send = _send_mock()
    seq = _seq_mock()
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)
    fake_client = MagicMock()
    fake_client.send.side_effect = ResendApiError("boom")

    with pytest.raises(OutreachSenderError, match="Resend send falló"):
        OutreachSenderAgent(client=fake_client).run(_ctx(fake_session))
    assert send.status == OutreachSendStatus.FAILED


# --- v0.14.0: snapshot HTML pasado a Resend ---


def test_sender_passes_body_html_when_present(fake_session) -> None:
    """Si el send tiene snapshot HTML, el sender lo manda como body_html."""
    send = _send_mock(body_html_rendered="<p>Hola HTML</p>")
    seq = _seq_mock(status=OutreachSequenceStatus.READY)
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)

    fake_client = MagicMock()
    fake_client.send.return_value = ResendSendResult(message_id="re_html", status="queued")

    OutreachSenderAgent(client=fake_client).run(_ctx(fake_session))

    call = fake_client.send.call_args
    assert call.kwargs["body_html"] == "<p>Hola HTML</p>"
    assert call.kwargs["body_text"] == "Cuerpo"


def test_sender_passes_none_body_html_for_legacy_sends(fake_session) -> None:
    """Sends pre-v0.14.0 (body_html_rendered NULL) → body_html=None."""
    send = _send_mock(body_html_rendered=None)
    seq = _seq_mock(status=OutreachSequenceStatus.READY)
    lead = _lead_mock()
    _setup_session(fake_session, send, seq, lead)

    fake_client = MagicMock()
    fake_client.send.return_value = ResendSendResult(message_id="re_legacy", status="queued")

    OutreachSenderAgent(client=fake_client).run(_ctx(fake_session))

    call = fake_client.send.call_args
    assert call.kwargs["body_html"] is None
