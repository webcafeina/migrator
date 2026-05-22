"""Tests del BriefRefinementAgent (Sprint v0.27.0 B2).

Mockea OpenAIClient.generate_brief_refinement + sesión SQLAlchemy.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.brief_refinement import BriefRefinementAgent
from wcm_worker.errors import (
    BriefRefinementError,
    OpenAIClientError,
)
from wcm_worker.integrations.openai_client import OpenAIResult


def _project(*, id: int = 42, brief_json: dict | None = None) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.brief_json = brief_json
    p.brief_refinement_proposals_json = None
    return p


def _ctx(fake_session, project, bricks_pages=None):
    fake_session.get.return_value = project
    pages = bricks_pages or []
    fake_session.execute.return_value.scalars.return_value = iter(pages)
    return AgentContext(session=fake_session, project_id=project.id)


def _brief() -> dict:
    return {
        "business": {
            "name": "Acme",
            "description": "Estudio creativo",
            "sector": "agency",
            "tone_of_voice": "premium",
        },
        "brand": {"colors": {"primary": "#000"}, "fonts": {}},
        "pages": [
            {
                "slug": "home",
                "title": "Home",
                "intent": "landing",
                "sections": [
                    {"type": "hero", "design_method": "ai", "headline": "Bienvenido"},
                    {"type": "cta", "design_method": "templates",
                     "cta_text": "Contacta", "cta_url": "/contact"},
                ],
            }
        ],
    }


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(BriefRefinementError, match="project_id"):
        BriefRefinementAgent().run(AgentContext(session=fake_session))


def test_skipped_sin_brief(fake_session) -> None:
    project = _project(brief_json=None)
    ctx = _ctx(fake_session, project)
    result = BriefRefinementAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_brief"


def test_skipped_sin_openai_key(fake_session, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    project = _project(brief_json=_brief())
    ctx = _ctx(fake_session, project)
    result = BriefRefinementAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_openai_key"


# ---------- happy path ----------


def test_persiste_propuestas_en_brief_refinement_proposals_json(fake_session) -> None:
    project = _project(brief_json=_brief())
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_brief_refinement = AsyncMock(
        return_value=OpenAIResult(
            data={
                "proposals": [
                    {
                        "id": "p1",
                        "category": "copy",
                        "page_slug": "home",
                        "section_index": 0,
                        "before": {"key": "headline", "value": "Bienvenido"},
                        "after": {"key": "headline", "value": "Diseña tu marca"},
                        "rationale": "Más específico al sector creativo.",
                        "impact_estimate": "high",
                    },
                    {
                        "id": "p2",
                        "category": "cta",
                        "page_slug": "home",
                        "section_index": 1,
                        "before": {"cta_text": "Contacta", "cta_url": "/contact"},
                        "after": {"cta_text": "Pide presupuesto gratuito",
                                  "cta_url": "/contact"},
                        "rationale": "Reduce fricción + promesa explícita.",
                        "impact_estimate": "medium",
                    },
                ]
            },
            tokens_in=1500,
            tokens_out=400,
            cost_usd=0.0195,
            model="gpt-5.5",
        )
    )

    result = BriefRefinementAgent(openai_client=client).run(ctx)

    assert client.generate_brief_refinement.call_count == 1
    assert result.outputs["skipped"] is False
    assert result.outputs["proposals_count"] == 2
    assert abs(result.outputs["cost_usd"] - 0.0195) < 1e-9
    # Persistido en project.
    proposals_data = project.brief_refinement_proposals_json
    assert proposals_data["model"] == "gpt-5.5"
    assert len(proposals_data["proposals"]) == 2
    # Cada propuesta tiene applied_at=None inicial.
    for p in proposals_data["proposals"]:
        assert "applied_at" in p
        assert p["applied_at"] is None


def test_openai_falla_no_borra_propuestas_anteriores(fake_session) -> None:
    """Si la nueva batch falla, conservamos las propuestas previas."""
    previous = {
        "generated_at": "2026-05-21T10:00:00Z",
        "model": "gpt-5.5",
        "cost_usd": 0.02,
        "proposals": [{"id": "old1", "applied_at": None}],
    }
    project = _project(brief_json=_brief())
    project.brief_refinement_proposals_json = previous
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_brief_refinement = AsyncMock(
        side_effect=OpenAIClientError("rate limit")
    )

    result = BriefRefinementAgent(openai_client=client).run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "openai_failed"
    # No tocó las anteriores.
    assert project.brief_refinement_proposals_json is previous


# ---------- pages_summary builder ----------


def test_build_pages_summary_compacto() -> None:
    """El summary NO incluye bricks_json crudo, solo metadata textual."""
    brief = _brief()
    bp = MagicMock()
    bp.wp_post_id = 100
    bp_by_slug = {"home": bp}
    summary = BriefRefinementAgent._build_pages_summary(brief, bp_by_slug)
    assert summary == [
        {
            "slug": "home",
            "title": "Home",
            "intent": "landing",
            "deployed_to_wp": True,
            "sections": [
                {
                    "type": "hero",
                    "design_method": "ai",
                    "headline": "Bienvenido",
                    "has_image": False,
                },
                {
                    "type": "cta",
                    "design_method": "templates",
                    "cta_text": "Contacta",
                    "cta_url": "/contact",
                    "has_image": False,
                },
            ],
        },
    ]


def test_build_pages_summary_has_image_true_si_asset_o_url() -> None:
    brief = {
        "pages": [{
            "slug": "p",
            "title": "P",
            "intent": "x",
            "sections": [
                {"type": "hero", "asset_id": 5},
                {"type": "hero", "image_url": "https://x"},
                {"type": "hero"},
            ],
        }]
    }
    summary = BriefRefinementAgent._build_pages_summary(brief, {})
    has_image_flags = [s["has_image"] for s in summary[0]["sections"]]
    assert has_image_flags == [True, True, False]
