"""Tests de los schemas Pydantic — validación, defaults, conversión."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest
from pydantic import ValidationError

from wcm_types import (
    AssetStatus,
    BlockType,
    BuilderType,
    ContentBlockSource,
    LeadStatus,
    OutreachChannel,
    OutreachSequenceStatus,
    ProjectStatus,
    ResidualCategory,
    ResidualStatus,
    UserRole,
)
from wcm_types.schemas.content_blocks import ContentBlockCreate
from wcm_types.schemas.leads import LeadCreate, LeadEnrichmentCreate, LeadRead
from wcm_types.schemas.outreach import OutreachSequenceCreate, OutreachStep
from wcm_types.schemas.projects import ProjectCreate
from wcm_types.schemas.users import UserCreate


def test_lead_create_minimal_valid() -> None:
    lead = LeadCreate(url="https://example.com/")
    assert str(lead.url) == "https://example.com/"
    assert lead.country == "ES"


def test_lead_create_invalid_url_rejected() -> None:
    with pytest.raises(ValidationError):
        LeadCreate(url="not-a-url")


def test_lead_create_country_two_chars() -> None:
    with pytest.raises(ValidationError):
        LeadCreate(url="https://example.com/", country="ESPAÑA")


def test_lead_read_serialization_excludes_embedding() -> None:
    """LeadRead no expone embedding ni embedding raw."""
    payload = {
        "id": 1,
        "url": "https://example.com/",
        "business_name": "Ejemplo SL",
        "sector": "restauración",
        "country": "ES",
        "region": "Andalucía",
        "builder_detected": BuilderType.WIX,
        "builder_confidence": 0.92,
        "builder_evidence": [{"level": 1, "signal": "header"}],
        "emails": ["info@ejemplo.com"],
        "phones": ["+34 600 000 000"],
        "social_links": {"linkedin": "https://linkedin.com/company/ejemplo"},
        "status": LeadStatus.ENRICHED,
        "score": 45,
        "last_crawl_at": datetime.now(UTC),
        "embedding_model": "voyage-multilingual-2",
        "embedding_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    lead = LeadRead.model_validate(payload)
    dump = lead.model_dump()
    assert "embedding" not in dump  # nunca se expone
    assert dump["status"] == "enriched"


def test_user_create_password_min_length() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="user@webcafeina.com", name="Test", password="short")


def test_project_create_defaults() -> None:
    project = ProjectCreate(client_name="Demo S.L.", source_url="https://demo.example/")
    assert project.has_ecommerce is False
    assert project.is_multilang is False
    assert project.asset_storage == "wp_local"
    assert project.preserve_paths is True


def test_project_create_asset_storage_validation() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(
            client_name="Demo S.L.",
            source_url="https://demo.example/",
            asset_storage="s3",
        )


def test_outreach_sequence_step_index_non_negative() -> None:
    with pytest.raises(ValidationError):
        OutreachStep(step_index=-1, body="hola")


def test_outreach_sequence_create_valid() -> None:
    seq = OutreachSequenceCreate(
        lead_id=1,
        template_name="wix-corporate-3steps",
        name="Outreach Demo",
        channel=OutreachChannel.EMAIL,
        steps_json=[
            OutreachStep(step_index=0, subject="Hola", body="Mensaje", delay_days_from_previous=0),
            OutreachStep(step_index=1, subject="Recordatorio", body="Mensaje 2", delay_days_from_previous=4),
        ],
    )
    assert seq.channel == OutreachChannel.EMAIL
    assert len(seq.steps_json) == 2


def test_content_block_create_requires_page_and_project() -> None:
    block = ContentBlockCreate(
        project_id=1,
        page_id=1,
        block_type=BlockType.HERO,
        order_index=0,
        content_json={"headline": "Hola"},
    )
    assert block.source == ContentBlockSource.EXTRACTED


def test_enums_are_str_values() -> None:
    """StrEnum garantiza que el .value es str y comparable a string crudo."""
    assert LeadStatus.DISCOVERED == "discovered"
    assert AssetStatus.READY == "ready"
    assert OutreachSequenceStatus.DRAFT_PENDING_REVIEW == "draft_pending_review"
    assert ProjectStatus.QA_FAILED == "qa_failed"
    assert UserRole.OPERATOR == "operator"
    assert ResidualCategory.BLOCKING_GO_LIVE == "blocking_go_live"
    assert ResidualStatus.OPEN == "open"


def test_lead_enrichment_create_traffic_non_negative() -> None:
    with pytest.raises(ValidationError):
        LeadEnrichmentCreate(lead_id=1, source="google_maps", traffic_estimate_monthly=-10)
