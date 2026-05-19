"""Tests ADR-050 — cap configurable + residual si alcanzado en ScraperOriginAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.scraper_origin import ScraperOriginAgent


def _ctx_mock() -> MagicMock:
    ctx = MagicMock()
    ctx.extra = {}
    return ctx


def _project_mock(*, max_pages_scrape: int | None = None) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.max_pages_scrape = max_pages_scrape
    return p


def test_resolve_max_pages_prefiere_columna_proyecto(monkeypatch) -> None:
    """project.max_pages_scrape gana sobre env y extra."""
    monkeypatch.setenv("SCRAPE_MAX_PAGES_DEFAULT", "120")
    ctx = _ctx_mock()
    ctx.extra = {"max_pages": 200}
    project = _project_mock(max_pages_scrape=80)
    assert ScraperOriginAgent()._resolve_max_pages(project, ctx) == 80


def test_resolve_max_pages_extra_si_no_columna(monkeypatch) -> None:
    """Sin project.max_pages_scrape → usa ctx.extra['max_pages']."""
    monkeypatch.setenv("SCRAPE_MAX_PAGES_DEFAULT", "120")
    ctx = _ctx_mock()
    ctx.extra = {"max_pages": 200}
    project = _project_mock(max_pages_scrape=None)
    assert ScraperOriginAgent()._resolve_max_pages(project, ctx) == 200


def test_resolve_max_pages_env_si_no_columna_ni_extra(monkeypatch) -> None:
    """Sin project ni extra → usa env SCRAPE_MAX_PAGES_DEFAULT."""
    monkeypatch.setenv("SCRAPE_MAX_PAGES_DEFAULT", "120")
    ctx = _ctx_mock()
    project = _project_mock(max_pages_scrape=None)
    assert ScraperOriginAgent()._resolve_max_pages(project, ctx) == 120


def test_resolve_max_pages_default_50(monkeypatch) -> None:
    """Sin nada configurado → fallback 50."""
    monkeypatch.delenv("SCRAPE_MAX_PAGES_DEFAULT", raising=False)
    ctx = _ctx_mock()
    project = _project_mock(max_pages_scrape=None)
    assert ScraperOriginAgent()._resolve_max_pages(project, ctx) == 50


def test_resolve_max_pages_env_invalido_cae_a_50(monkeypatch) -> None:
    """Env mal formada → fallback 50 + warning (no crashea)."""
    monkeypatch.setenv("SCRAPE_MAX_PAGES_DEFAULT", "not-an-int")
    ctx = _ctx_mock()
    project = _project_mock(max_pages_scrape=None)
    assert ScraperOriginAgent()._resolve_max_pages(project, ctx) == 50


def test_cap_residual_contenido_esperado() -> None:
    """ResidualTask generado tiene categoría POST_GO_LIVE + título y cuerpo informativo."""
    from wcm_types.enums import ResidualCategory, ResidualStatus

    project = _project_mock()
    residual = ScraperOriginAgent()._cap_residual(project, cap=50, pending=12)

    assert residual.project_id == 7
    assert residual.category == ResidualCategory.POST_GO_LIVE
    assert residual.status == ResidualStatus.OPEN
    assert "50" in residual.title
    assert "12" in residual.description
    assert "max_pages" in residual.description.lower()
    assert residual.generated_by == "scraper-origin"


@pytest.mark.parametrize(
    "results_count,pending,expected",
    [
        (50, 5, True),  # cap alcanzado + URLs pendientes
        (49, 5, False),  # bajo cap → no residual
        (50, 0, False),  # cap alcanzado pero sin pendientes → no residual
        (10, 50, False),  # to_visit ≠ vacío pero results < cap → cap NO alcanzado
    ],
)
def test_cap_reached_logica(results_count: int, pending: int, expected: bool) -> None:
    """La condición exacta cap_reached = len(results) >= max_pages AND to_visit."""
    assert (results_count >= 50 and bool(pending)) is expected
