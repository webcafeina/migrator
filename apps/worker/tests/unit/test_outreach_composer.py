"""Tests del OutreachComposerAgent — sin tocar DB real.

Cubrimos: validación de inputs, render Jinja2, validación legal estricta,
detección de opt-out previo, persistencia de sequence + sends.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_types.enums import (
    BuilderType,
    LeadStatus,
    OutreachSequenceStatus,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.outreach_composer import (
    LEGAL_VALIDATOR_VERSION,
    OutreachComposerAgent,
    _builder_to_label,
    _city_from_address,
    _validate_legal_compliance,
)
from wcm_worker.errors import OutreachComposerError


_COMPANY = {
    "legal_name": "Webcafeína S.L.",
    "cif": "B10463990",
    "address": "Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres",
    "contact_email": "info@webcafeina.com",
    "privacy_url": "https://webcafeina.com/politica-privacidad/",
    "opt_out_url_base": "https://migrator.webcafeina.com/opt-out",
}


def _lead_mock(*, lead_id: int = 1, emails: list[str] | None = None) -> MagicMock:
    lead = MagicMock()
    lead.id = lead_id
    lead.url = "https://barpepe.es"
    lead.business_name = "Bar Pepe"
    lead.sector = "restauración"
    lead.region = "Cáceres"
    lead.emails = emails if emails is not None else ["hola@barpepe.es"]
    lead.builder_detected = BuilderType.WIX
    lead.status = LeadStatus.ENRICHED
    return lead


def _ctx_for(session, lead_id: int, *, token: str = "tk-123",
             steps: list | None = None) -> AgentContext:
    return AgentContext(
        session=session,
        lead_id=lead_id,
        extra={
            "company": _COMPANY,
            "opt_out_token": token,
            "steps": steps,
        },
    )


def _no_optout_in_db(fake_session) -> None:
    """Configura session.execute para que opt_out_log esté vacío."""
    res = MagicMock()
    res.first.return_value = None
    fake_session.execute.return_value = res


def test_composer_requires_lead_id(fake_session) -> None:
    with pytest.raises(OutreachComposerError, match="lead_id"):
        OutreachComposerAgent().run(AgentContext(session=fake_session))


def test_composer_lead_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(OutreachComposerError, match="no encontrado"):
        OutreachComposerAgent().run(
            AgentContext(session=fake_session, lead_id=99, extra={"opt_out_token": "x"})
        )


def test_composer_requires_email(fake_session) -> None:
    lead = _lead_mock(emails=[])
    fake_session.get.return_value = lead
    with pytest.raises(OutreachComposerError, match="sin email"):
        OutreachComposerAgent().run(_ctx_for(fake_session, 1))


def test_composer_requires_opt_out_token(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    _no_optout_in_db(fake_session)
    ctx = AgentContext(
        session=fake_session,
        lead_id=1,
        extra={"company": _COMPANY},  # falta opt_out_token
    )
    with pytest.raises(OutreachComposerError, match="opt_out_token"):
        OutreachComposerAgent().run(ctx)


def test_composer_aborts_when_lead_previously_opted_out(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead

    res = MagicMock()
    res.first.return_value = ("hola@barpepe.es",)
    fake_session.execute.return_value = res

    with pytest.raises(OutreachComposerError, match="opted-out"):
        OutreachComposerAgent().run(_ctx_for(fake_session, 1))
    assert lead.status == LeadStatus.OPTED_OUT


def test_composer_persists_sequence_and_sends(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    _no_optout_in_db(fake_session)

    # session.flush asigna IDs en SQLAlchemy real. Aquí hookeamos add para
    # asignarle un id al primer OutreachSequence visto.
    added = []
    def _add(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 77
        added.append(obj)
    fake_session.add.side_effect = _add

    result = OutreachComposerAgent().run(_ctx_for(fake_session, 1))

    seq_objs = [o for o in added if type(o).__name__ == "OutreachSequence"]
    send_objs = [o for o in added if type(o).__name__ == "OutreachSend"]
    audit_objs = [o for o in added if type(o).__name__ == "AuditLog"]

    assert len(seq_objs) == 1
    assert seq_objs[0].status == OutreachSequenceStatus.DRAFT_PENDING_REVIEW
    assert seq_objs[0].legal_validation_passed is True
    assert seq_objs[0].legal_validator_version == LEGAL_VALIDATOR_VERSION
    assert len(send_objs) == 2  # secuencia default = intro + followup
    assert all("opt-out" in (s.body_rendered or "") for s in send_objs)
    assert all(_COMPANY["cif"] in (s.body_rendered or "") for s in send_objs)
    assert lead.status == LeadStatus.OUTREACH_PREPARED
    assert result.outputs["sequence_id"] == 77
    assert audit_objs, "Debe registrar audit_log de creación de la secuencia"


def test_validate_legal_compliance_catches_missing_cif() -> None:
    bad_body = "Hola, " + _COMPANY["legal_name"] + " " + _COMPANY["address"]
    bad_body += " " + _COMPANY["opt_out_url_base"] + "?token=x"
    steps = [{"subject": "asunto", "body": bad_body}]
    errors = _validate_legal_compliance(steps, _COMPANY)
    assert any("CIF" in e for e in errors)


def test_validate_legal_compliance_catches_missing_optout() -> None:
    body = (
        f"{_COMPANY['legal_name']} {_COMPANY['cif']} {_COMPANY['address']}. "
        "Hola."  # sin opt-out url
    )
    steps = [{"subject": "asunto", "body": body}]
    errors = _validate_legal_compliance(steps, _COMPANY)
    assert any("opt-out" in e for e in errors)


def test_validate_legal_compliance_passes_when_all_present() -> None:
    body = (
        f"{_COMPANY['legal_name']} · CIF {_COMPANY['cif']} · "
        f"{_COMPANY['address']} · {_COMPANY['contact_email']}. "
        f"Opt-out: {_COMPANY['opt_out_url_base']}?token=x"
    )
    steps = [{"subject": "asunto", "body": body}]
    errors = _validate_legal_compliance(steps, _COMPANY)
    assert errors == []


def test_builder_to_label_maps_wix() -> None:
    assert _builder_to_label(BuilderType.WIX) == "Wix"
    assert _builder_to_label(BuilderType.HOSTINGER_AI) == "Hostinger AI Builder"
    assert _builder_to_label(None) == "vuestra plataforma actual"


def test_city_from_address_extracts_caceres() -> None:
    assert _city_from_address(
        "Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres"
    ) == "Cáceres"
    assert _city_from_address("") == ""
