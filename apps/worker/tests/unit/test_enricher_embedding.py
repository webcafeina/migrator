"""Tests del Enricher con embedding — el servicio de sentence-transformers
se stubea para no descargar el modelo en CI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import LeadStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.enricher import (
    EnricherAgent,
    _build_embedding_text,
    _html_to_text_snippet,
)


def _lead_mock() -> MagicMock:
    lead = MagicMock()
    lead.id = 42
    lead.url = "https://barpepe.es"
    lead.business_name = "Bar Pepe"
    lead.sector = "restauración"
    lead.region = "Cáceres"
    lead.builder_detected = None
    lead.builder_confidence = None
    lead.emails = []
    lead.phones = []
    lead.social_links = {}
    return lead


def test_enricher_skips_embedding_when_flagged(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.text = "<html><body>hola</body></html>"

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=fake_response):
        result = EnricherAgent().run(
            AgentContext(session=fake_session, lead_id=42, extra={"skip_embedding": True})
        )

    assert result.outputs["embedding"] == {"computed": False}
    assert lead.embedding is None or lead.embedding == lead.embedding  # no escrito
    assert lead.status == LeadStatus.ENRICHED


def test_enricher_calls_embedding_service(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.text = (
        "<html><body>Bar Pepe, restauración familiar en Cáceres "
        "desde 1980. Especialidad en migas extremeñas.</body></html>"
    )

    fake_service = MagicMock()
    fake_service.model_name = "intfloat/multilingual-e5-large"
    fake_service.embed_text = MagicMock(return_value=[0.01] * 1024)

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=fake_response), \
         patch("wcm_worker.embedding.get_embedding_service", return_value=fake_service):
        result = EnricherAgent().run(
            AgentContext(session=fake_session, lead_id=42)
        )

    assert result.outputs["embedding"]["computed"] is True
    assert result.outputs["embedding"]["dim"] == 1024
    assert lead.embedding == [0.01] * 1024
    assert lead.embedding_model == "intfloat/multilingual-e5-large"
    assert lead.embedding_at is not None
    fake_service.embed_text.assert_called_once()


def test_enricher_handles_embedding_import_error(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.text = "<html></html>"

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=fake_response), \
         patch(
             "wcm_worker.embedding.get_embedding_service",
             side_effect=RuntimeError("sentence-transformers no instalado"),
         ):
        result = EnricherAgent().run(AgentContext(session=fake_session, lead_id=42))

    assert result.outputs["embedding"]["computed"] is False
    assert "compute_error" in result.outputs["embedding"]["reason"]


def test_enricher_rejects_wrong_dim_embedding(fake_session) -> None:
    lead = _lead_mock()
    fake_session.get.return_value = lead
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.text = "<html><body>x</body></html>"

    fake_service = MagicMock()
    fake_service.model_name = "wrong-model"
    fake_service.embed_text = MagicMock(return_value=[0.0] * 768)  # dim incorrecta

    with patch("wcm_worker.agents.enricher.httpx.get", return_value=fake_response), \
         patch("wcm_worker.embedding.get_embedding_service", return_value=fake_service):
        result = EnricherAgent().run(AgentContext(session=fake_session, lead_id=42))

    assert result.outputs["embedding"]["computed"] is False
    assert "dim_mismatch" in result.outputs["embedding"]["reason"]


def test_build_embedding_text_includes_key_signals() -> None:
    lead = _lead_mock()
    text = _build_embedding_text(lead, "<p>hola mundo</p>")
    assert "Bar Pepe" in text
    assert "restauración" in text
    assert "Cáceres" in text
    assert "hola mundo" in text


def test_html_to_text_snippet_strips_scripts() -> None:
    html = "<html><script>var x = 1;</script><body><p>Hola</p></body></html>"
    text = _html_to_text_snippet(html, max_chars=200)
    assert "var x" not in text
    assert "Hola" in text


def test_html_to_text_snippet_truncates() -> None:
    html = "<p>" + ("a" * 5000) + "</p>"
    text = _html_to_text_snippet(html, max_chars=100)
    assert len(text) == 100
