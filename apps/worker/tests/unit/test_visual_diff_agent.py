"""Tests del VisualDiffAgent (v0.16.0).

Estrategia: mockear Playwright (NO instalado en CI, SKIPPED path) +
mockear R2Client + mockear scraped_pages. Tests separados:
- `test_visual_diff_compare.py` cubre el helper de pixelmatch
  (sin red ni screenshots).
- Aquí cubrimos el control flow del agent: required project,
  Playwright no disponible, fallback con session real.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.visual_diff import (
    VisualDiffAgent,
    _build_target_url,
    _extract_path,
    _slugify,
)
from wcm_worker.errors import VisualDiffError
from wcm_worker.integrations.playwright_screenshot import PlaywrightNotAvailableError


def _project_mock(*, target_domain: str | None = "barpepe.es") -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.target_domain = target_domain
    p.visual_diff_avg_score = None
    return p


def _page_mock(*, url: str = "https://barpepe.es/", page_id: int = 1) -> MagicMock:
    page = MagicMock()
    page.id = page_id
    page.url = url
    page.depth = 0
    page.status = ScrapeStatus.SUCCESS
    return page


def test_helper_extract_path_root() -> None:
    assert _extract_path("https://barpepe.es/") == "/"


def test_helper_extract_path_nested() -> None:
    assert _extract_path("https://barpepe.es/blog/post-1") == "/blog/post-1"


def test_helper_build_target_url_sin_protocolo() -> None:
    assert _build_target_url("foo.es", "/contacto") == "https://foo.es/contacto"


def test_helper_build_target_url_con_protocolo() -> None:
    assert _build_target_url("https://foo.es/", "/x") == "https://foo.es/x"


def test_helper_slugify_root() -> None:
    assert _slugify("/") == "root"
    assert _slugify("") == "root"


def test_helper_slugify_nested() -> None:
    assert _slugify("/blog/post-1") == "blog-post-1"
    assert _slugify("/x/y/z") == "x-y-z"


def test_agent_requires_project_id(fake_session) -> None:
    agent = VisualDiffAgent()
    with pytest.raises(VisualDiffError, match="project_id"):
        agent.run(AgentContext(session=fake_session))


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(VisualDiffError, match="no encontrado"):
        VisualDiffAgent().run(AgentContext(session=fake_session, project_id=99))


def test_agent_project_sin_target_domain(fake_session) -> None:
    fake_session.get.return_value = _project_mock(target_domain=None)
    with pytest.raises(VisualDiffError, match="target_domain"):
        VisualDiffAgent().run(AgentContext(session=fake_session, project_id=7))


def test_agent_sin_paginas_completa_con_warning(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = res

    result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=7))
    assert result.outputs["pages_compared"] == 0
    assert "scraped_pages vacío" in result.warnings[0]


def test_agent_playwright_no_disponible_marca_skipped(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    # Pre-check D.1 hace `httpx.get(target_url)` antes de Playwright.
    # En CI no hay barpepe.es real, mockear con 200 para que el flujo
    # llegue a la rama Playwright failed (que es lo que valida este test).
    fake_response = MagicMock()
    fake_response.status_code = 200
    with patch("wcm_worker.agents.visual_diff.httpx.get", return_value=fake_response), \
         patch("wcm_worker.agents.visual_diff.screenshot_session") as mock_session:
        mock_session.side_effect = PlaywrightNotAvailableError("chromium missing")
        result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=7))

    assert result.outputs["skipped"] is True
    assert "Playwright" in result.summary
