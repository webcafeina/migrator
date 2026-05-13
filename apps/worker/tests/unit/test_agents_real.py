"""Tests de subagentes REAL con mocks de sus dependencias.

Cobertura: signature de cada `.run(ctx)`, manejo de errores tipados,
persistencia mínima en DB mockeada.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.enricher import EnricherAgent, _compute_score, _normalize_phone
from wcm_worker.agents.fingerprinter import FingerprinterAgent
from wcm_worker.errors import EnricherError, FingerprinterError


# ---------- helpers ----------

def _lead_mock(
    *,
    lead_id: int = 1,
    url: str = "https://www.example-wix.com/",
    builder_detected=None,
    builder_confidence=None,
    sector: str | None = "restaurante",
):
    lead = MagicMock()
    lead.id = lead_id
    lead.url = url
    lead.builder_detected = builder_detected
    lead.builder_confidence = builder_confidence
    lead.emails = []
    lead.phones = []
    lead.social_links = {}
    lead.sector = sector
    return lead


# ---------- FingerprinterAgent ----------

def test_fingerprinter_requires_lead_id(fake_session) -> None:
    agent = FingerprinterAgent()
    with pytest.raises(FingerprinterError, match="lead_id"):
        agent.run(AgentContext(session=fake_session))


def test_fingerprinter_lead_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    agent = FingerprinterAgent()
    with pytest.raises(FingerprinterError, match="no encontrado"):
        agent.run(AgentContext(session=fake_session, lead_id=999))


def test_fingerprinter_unreachable_url(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead

    with patch("wcm_worker.agents.fingerprinter.httpx.get") as mock_get:
        mock_get.side_effect = httpx.RequestError("dns")
        agent = FingerprinterAgent()
        with pytest.raises(FingerprinterError, match="inalcanzable"):
            agent.run(AgentContext(session=fake_session, lead_id=1))


def test_fingerprinter_wix_detected_persists(fake_session) -> None:
    from wcm_types.enums import BuilderType

    lead = _lead_mock()
    fake_session.get.return_value = lead

    wix_html = """
    <html>
      <head><meta name="generator" content="Wix.com Website Builder"></head>
      <body>
        <div id="SITE_CONTAINER">
          <script src="https://static.parastorage.com/services/x.js"></script>
        </div>
      </body>
    </html>
    """
    response = MagicMock()
    response.text = wix_html
    response.headers = {"x-wix-request-id": "abc"}

    with patch("wcm_worker.agents.fingerprinter.httpx.get", return_value=response):
        agent = FingerprinterAgent()
        result = agent.run(AgentContext(session=fake_session, lead_id=1))

    assert lead.builder_detected == BuilderType.WIX
    assert lead.builder_confidence > 0.5
    assert "wix" in result.summary


def test_fingerprinter_unknown_when_no_match(fake_session) -> None:
    from wcm_types.enums import BuilderType

    lead = _lead_mock()
    fake_session.get.return_value = lead

    response = MagicMock()
    response.text = "<html><body>Hola mundo</body></html>"
    response.headers = {}

    with patch("wcm_worker.agents.fingerprinter.httpx.get", return_value=response):
        agent = FingerprinterAgent()
        agent.run(AgentContext(session=fake_session, lead_id=1))

    assert lead.builder_detected == BuilderType.UNKNOWN
    assert lead.builder_confidence == 0.0


# ---------- EnricherAgent ----------

def test_enricher_extracts_emails_and_socials(fake_session) -> None:
    lead = _lead_mock(url="https://example.com/")
    fake_session.get.return_value = lead

    html_with_data = """
    <html><body>
      <p>Contacto: hola@example.com - +34 612 345 678</p>
      <a href="https://linkedin.com/company/example">LinkedIn</a>
    </body></html>
    """
    response = MagicMock()
    response.status_code = 200
    response.text = html_with_data

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=response):
        agent = EnricherAgent()
        result = agent.run(AgentContext(session=fake_session, lead_id=1))

    assert "hola@example.com" in lead.emails
    assert any("612" in p for p in lead.phones)
    assert "linkedin" in lead.social_links
    assert lead.score > 0


def test_enricher_filters_placeholder_emails(fake_session) -> None:
    lead = _lead_mock(url="https://example.com/")
    fake_session.get.return_value = lead

    response = MagicMock()
    response.status_code = 200
    response.text = "<html>info@example.com real@miempresa.com</html>"

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=response):
        agent = EnricherAgent()
        agent.run(AgentContext(session=fake_session, lead_id=1))

    assert "info@example.com" not in lead.emails
    assert "real@miempresa.com" in lead.emails


def test_normalize_phone_adds_es_prefix() -> None:
    assert _normalize_phone("612 345 678") == "+34612345678"
    assert _normalize_phone("+34 612 345 678") == "+34612345678"


def test_compute_score_caps_at_100() -> None:
    lead = _lead_mock(builder_detected=MagicMock(), builder_confidence=0.9, sector="x")
    lead.emails = ["a@b.com"]
    lead.phones = ["+34..."]
    lead.social_links = {"linkedin": "x"}
    score = _compute_score(lead)
    assert 0 <= score <= 100
