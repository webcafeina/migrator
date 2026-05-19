"""Tests del QaRunnerAgent (v0.16.0)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.qa_runner import (
    QaRunnerAgent,
    _avg_or_none,
    _build_base_url,
    _strip_protocol,
)
from wcm_worker.errors import QaRunnerError
from wcm_worker.integrations.lighthouse import LighthouseResult
from wcm_worker.integrations.link_checker import LinkReport


def _project_mock(*, target_domain: str | None = "target.test") -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.target_domain = target_domain
    return p


def test_helper_strip_protocol() -> None:
    assert _strip_protocol("https://foo.es") == "foo.es"
    assert _strip_protocol("http://foo.es/") == "foo.es"
    assert _strip_protocol("foo.es") == "foo.es"


def test_helper_build_base_url() -> None:
    assert _build_base_url("foo.es") == "https://foo.es/"
    assert _build_base_url("https://foo.es") == "https://foo.es/"


def test_helper_avg_or_none() -> None:
    assert _avg_or_none(80, 90) == 85
    assert _avg_or_none(None, 70) == 70
    assert _avg_or_none(None, None) is None
    assert _avg_or_none() is None


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(QaRunnerError, match="project_id"):
        QaRunnerAgent().run(AgentContext(session=fake_session))


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(QaRunnerError, match="no encontrado"):
        QaRunnerAgent().run(AgentContext(session=fake_session, project_id=99))


def test_agent_project_sin_target_domain(fake_session) -> None:
    fake_session.get.return_value = _project_mock(target_domain=None)
    with pytest.raises(QaRunnerError, match="target_domain"):
        QaRunnerAgent().run(AgentContext(session=fake_session, project_id=7))


def test_agent_lighthouse_no_disponible_genera_residual(fake_session) -> None:
    """Sin Lighthouse → scores=null + residual task 'instalar lighthouse'."""
    fake_session.get.return_value = _project_mock()
    # Sin scraped_pages para simplificar.
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result

    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)

    with patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=False):
        result = QaRunnerAgent(http_client=fake_http).run(
            AgentContext(session=fake_session, project_id=7)
        )

    # Residual task creada por Lighthouse no instalado.
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert len(residuals) >= 1
    assert any("Lighthouse" in r.title for r in residuals)
    assert "Lighthouse SKIPPED" in result.summary


def test_agent_happy_path_persiste_report(fake_session) -> None:
    """Mock Lighthouse OK + link_check OK + checks binarios OK."""
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result

    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)

    fake_lh = LighthouseResult(performance=85, accessibility=90, best_practices=92, seo=100)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch("wcm_worker.agents.qa_runner.check_links", return_value=LinkReport()),
        patch.object(
            QaRunnerAgent,
            "_check_https",
            return_value=True,
        ),
        patch.object(
            QaRunnerAgent,
            "_check_url_accessible",
            return_value=True,
        ),
    ):
        result = QaRunnerAgent(http_client=fake_http).run(
            AgentContext(session=fake_session, project_id=7)
        )

    added = [c.args[0] for c in fake_session.add.call_args_list]
    reports = [o for o in added if type(o).__name__ == "QaReport"]
    assert len(reports) == 1
    r = reports[0]
    assert r.lighthouse_perf_desktop == 85
    assert r.lighthouse_perf_mobile == 85
    assert r.https_valid is True
    assert r.robots_accessible is True
    assert r.sitemap_accessible is True
    # No residuals (todo verde).
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert len(residuals) == 0
    assert "85/100" in result.summary


# ADR-053 — thresholds nuevos a11y/bp/seo + broken links proporcional.


def test_adr053_a11y_bajo_genera_residual(fake_session) -> None:
    """a11y < 70 → ResidualTask POST_GO_LIVE."""
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result
    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)
    # a11y=60 < 70 dispara residual; otros OK.
    fake_lh = LighthouseResult(performance=85, accessibility=60, best_practices=92, seo=100)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch("wcm_worker.agents.qa_runner.check_links", return_value=LinkReport()),
        patch.object(QaRunnerAgent, "_check_https", return_value=True),
        patch.object(QaRunnerAgent, "_check_url_accessible", return_value=True),
    ):
        QaRunnerAgent(http_client=fake_http).run(AgentContext(session=fake_session, project_id=7))

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert any("accesibilidad" in r.title.lower() for r in residuals)
    assert any("60/100" in r.title for r in residuals)


def test_adr053_seo_bp_bajos_generan_residuales(fake_session) -> None:
    """best_practices < 75 + seo < 80 → 2 ResidualTask POST_GO_LIVE."""
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result
    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)
    fake_lh = LighthouseResult(performance=85, accessibility=90, best_practices=60, seo=70)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch("wcm_worker.agents.qa_runner.check_links", return_value=LinkReport()),
        patch.object(QaRunnerAgent, "_check_https", return_value=True),
        patch.object(QaRunnerAgent, "_check_url_accessible", return_value=True),
    ):
        QaRunnerAgent(http_client=fake_http).run(AgentContext(session=fake_session, project_id=7))

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    titles = [r.title for r in residuals]
    assert any("buenas prácticas" in t.lower() for t in titles)
    assert any("seo técnico" in t.lower() for t in titles)


def test_adr053_broken_links_proporcional_web_pequena(fake_session) -> None:
    """En web de 10 links, 3 broken supera threshold max(2, 10*3%)=2."""
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result
    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)
    fake_lh = LighthouseResult(performance=90, accessibility=90, best_practices=90, seo=90)
    link_report = LinkReport(broken=[], broken_count=3, total_checked=10)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch.object(QaRunnerAgent, "_check_links", return_value=link_report),
        patch.object(QaRunnerAgent, "_check_https", return_value=True),
        patch.object(QaRunnerAgent, "_check_url_accessible", return_value=True),
    ):
        QaRunnerAgent(http_client=fake_http).run(AgentContext(session=fake_session, project_id=7))

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    broken_residuals = [r for r in residuals if "Links rotos" in r.title]
    assert len(broken_residuals) == 1
    assert "3/10" in broken_residuals[0].title


def test_adr053_broken_links_proporcional_web_grande_no_dispara(fake_session) -> None:
    """En web de 500 links, 10 broken NO supera threshold max(2, 500*3%)=15."""
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result
    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)
    fake_lh = LighthouseResult(performance=90, accessibility=90, best_practices=90, seo=90)
    link_report = LinkReport(broken=[], broken_count=10, total_checked=500)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch.object(QaRunnerAgent, "_check_links", return_value=link_report),
        patch.object(QaRunnerAgent, "_check_https", return_value=True),
        patch.object(QaRunnerAgent, "_check_url_accessible", return_value=True),
    ):
        QaRunnerAgent(http_client=fake_http).run(AgentContext(session=fake_session, project_id=7))

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    broken_residuals = [r for r in residuals if "Links rotos" in r.title]
    assert len(broken_residuals) == 0  # 10 broken < threshold 15


def test_agent_https_invalido_genera_residual_blocking(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result
    fake_http = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_http.head = MagicMock(return_value=fake_resp)
    fake_lh = LighthouseResult(performance=85, accessibility=90, best_practices=92, seo=100)

    with (
        patch("wcm_worker.agents.qa_runner.lighthouse_available", return_value=True),
        patch("wcm_worker.agents.qa_runner.run_lighthouse", return_value=fake_lh),
        patch("wcm_worker.agents.qa_runner.check_links", return_value=LinkReport()),
        patch.object(QaRunnerAgent, "_check_https", return_value=False),
        patch.object(QaRunnerAgent, "_check_url_accessible", return_value=True),
    ):
        QaRunnerAgent(http_client=fake_http).run(AgentContext(session=fake_session, project_id=7))

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert any("HTTPS" in r.title for r in residuals)
