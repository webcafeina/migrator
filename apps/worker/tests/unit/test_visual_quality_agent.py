"""Tests del VisualQualityAgent (v0.28.0 B6)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.visual_quality import (
    VisualQualityAgent,
    score_from_probe,
)

# -----------------------------------------------------------------------------
# score_from_probe — función pura, sin Playwright
# -----------------------------------------------------------------------------


def test_score_full_when_all_signals_pass() -> None:
    """Página perfecta: bricks root + h1 grande sin serif + sections con padding."""
    probe = {
        "has_bricks_root": True,
        "h1_count": 1,
        "h1_default_font": 0,
        "h1_with_explicit_size": 1,
        "section_count": 3,
        "section_with_padding": 3,
    }
    score, failed = score_from_probe(probe)
    assert score == 1.00
    assert failed == []


def test_score_zero_when_default_wp_render() -> None:
    """Caso bug raíz E2E v0.27.0: WP renderiza con CSS default."""
    probe = {
        "has_bricks_root": False,
        "h1_count": 1,
        "h1_default_font": 1,  # h1 con Times/serif
        "h1_with_explicit_size": 0,  # 1em default ~16px
        "section_count": 0,
        "section_with_padding": 0,
    }
    score, failed = score_from_probe(probe)
    assert score == 0.0
    assert "no_bricks_root_class" in failed
    assert "h1_default_size" in failed
    assert "h1_default_serif_font" in failed


def test_score_partial_with_bricks_but_no_typography() -> None:
    """Bricks cargado pero theme styles no aplicados a h1."""
    probe = {
        "has_bricks_root": True,
        "h1_count": 1,
        "h1_default_font": 1,
        "h1_with_explicit_size": 0,
        "section_count": 2,
        "section_with_padding": 2,
    }
    score, failed = score_from_probe(probe)
    # 0.30 (bricks root) + 0.20 (sections) = 0.50
    assert score == 0.50
    assert "h1_default_size" in failed
    assert "h1_default_serif_font" in failed


def test_score_page_without_h1_marks_failed_signal() -> None:
    probe = {
        "has_bricks_root": True,
        "h1_count": 0,
        "h1_default_font": 0,
        "h1_with_explicit_size": 0,
        "section_count": 2,
        "section_with_padding": 2,
    }
    score, failed = score_from_probe(probe)
    assert "no_h1_in_page" in failed
    # 0.30 + 0.20 = 0.50
    assert score == 0.50


def test_score_sections_partial_padding() -> None:
    """Más de la mitad de sections sin padding → fail señal."""
    probe = {
        "has_bricks_root": True,
        "h1_count": 1,
        "h1_default_font": 0,
        "h1_with_explicit_size": 1,
        "section_count": 4,
        "section_with_padding": 1,  # 25% < 50%
    }
    score, failed = score_from_probe(probe)
    assert "sections_without_padding" in failed
    # 0.30 + 0.30 + 0.20 = 0.80
    assert score == 0.80


# -----------------------------------------------------------------------------
# Agent run() — con prober mock
# -----------------------------------------------------------------------------


def _make_ctx_with_pages(pages_data: list[tuple[str, int]]) -> AgentContext:
    """ctx con N bricks_pages mockeadas + project mock."""
    session = MagicMock()
    project = MagicMock()
    project.id = 42
    session.get.return_value = project

    pages = []
    for slug, wp_post_id in pages_data:
        bp = MagicMock()
        bp.slug = slug
        bp.wp_post_id = wp_post_id
        bp.project_id = 42
        pages.append(bp)

    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = pages
    session.execute.return_value = result_obj
    return AgentContext(session=session, project_id=42)


def test_agent_skipped_without_project_id() -> None:
    ctx = AgentContext(session=MagicMock(), project_id=None)
    res = VisualQualityAgent().run(ctx)
    assert res.outputs["skipped"] is True
    assert res.outputs["reason"] == "no_project_id"


def test_agent_skipped_without_pages() -> None:
    ctx = _make_ctx_with_pages([])
    res = VisualQualityAgent().run(ctx)
    assert res.outputs["skipped"] is True
    assert res.outputs["reason"] == "no_deployed_pages"


def test_agent_skipped_without_wp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WP_DEFAULT_SITE_URL", raising=False)
    ctx = _make_ctx_with_pages([("home", 1001)])
    res = VisualQualityAgent().run(ctx)
    assert res.outputs["skipped"] is True
    assert res.outputs["reason"] == "no_wp_target"


def test_agent_marks_pages_ok_above_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WP_DEFAULT_SITE_URL", "https://wp.example.com")
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "admin")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "xxxx")
    ctx = _make_ctx_with_pages([("home", 1001), ("about", 1002)])

    async def good_prober(url: str, target: dict) -> dict:
        return {
            "has_bricks_root": True,
            "h1_count": 1,
            "h1_default_font": 0,
            "h1_with_explicit_size": 1,
            "section_count": 3,
            "section_with_padding": 3,
        }

    agent = VisualQualityAgent(prober=good_prober, threshold=0.60)
    res = agent.run(ctx)
    assert res.outputs["pages_ok"] == 2
    assert res.outputs["pages_failed"] == 0
    assert res.outputs["global_ratio"] == 1.0
    assert res.residual_tasks_created == 0


def test_agent_emits_residual_when_score_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WP_DEFAULT_SITE_URL", "https://wp.example.com")
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "admin")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "xxxx")
    ctx = _make_ctx_with_pages([("home", 1001)])

    async def bad_prober(url: str, target: dict) -> dict:
        # Caso E2E v0.27.0: WP renderiza con CSS default
        return {
            "has_bricks_root": False,
            "h1_count": 1,
            "h1_default_font": 1,
            "h1_with_explicit_size": 0,
            "section_count": 0,
            "section_with_padding": 0,
        }

    agent = VisualQualityAgent(prober=bad_prober, threshold=0.60)
    res = agent.run(ctx)
    assert res.outputs["pages_ok"] == 0
    assert res.outputs["pages_failed"] == 1
    assert res.residual_tasks_created == 1
    assert res.outputs["page_scores"][0]["score"] == 0.0
    assert "no_bricks_root_class" in res.outputs["page_scores"][0]["failed_signals"]
    # Warning global
    assert any("ratio" in w.lower() for w in res.warnings)


def test_agent_handles_prober_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WP_DEFAULT_SITE_URL", "https://wp.example.com")
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "admin")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "xxxx")
    ctx = _make_ctx_with_pages([("home", 1001)])

    async def failing_prober(url: str, target: dict) -> dict:
        raise TimeoutError("Network unreachable")

    agent = VisualQualityAgent(prober=failing_prober)
    res = agent.run(ctx)
    assert res.outputs["pages_failed"] == 1
    assert res.outputs["pages_ok"] == 0
    assert any("probe failed" in w.lower() for w in res.warnings)


def test_threshold_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """WCM_VISUAL_QUALITY_THRESHOLD override aceptado."""
    monkeypatch.setenv("WCM_VISUAL_QUALITY_THRESHOLD", "0.85")
    agent = VisualQualityAgent()
    assert agent._threshold == 0.85
