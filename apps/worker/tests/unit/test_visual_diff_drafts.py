"""Tests del Bug D (visual_diff con páginas en draft) — fix 2026-05-20.

3 mecanismos defensivos cubiertos:
- D.1 pre-check HTTP antes de abrir Playwright → SKIPPED rápido si 404.
- D.2 timeout corto para captura del target (override per-call).
- D.3 cap de fallos consecutivos → abortar bucle para no quemar minutos.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.visual_diff import (
    DEFAULT_MAX_CONSECUTIVE_FAILURES,
    DEFAULT_TARGET_TIMEOUT_MS,
    PrecheckResult,
    VisualDiffAgent,
)


def _project_mock(*, target_domain: str = "test-migrator.webcafeina.com") -> MagicMock:
    p = MagicMock()
    p.id = 15
    p.target_domain = target_domain
    p.visual_diff_avg_score = None
    p.visual_diff_threshold = None
    return p


def _page_mock(*, url: str = "https://mariya.design/", page_id: int = 1) -> MagicMock:
    page = MagicMock()
    page.id = page_id
    page.url = url
    page.depth = 0
    page.status = ScrapeStatus.SUCCESS
    return page


# ---------- D.1 pre-check ----------


def test_precheck_404_devuelve_skip_drafts(fake_session) -> None:
    """Target devuelve 404 → SKIPPED + ResidualTask, sin abrir Playwright."""
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    fake_response = MagicMock()
    fake_response.status_code = 404

    with patch("wcm_worker.agents.visual_diff.httpx.get", return_value=fake_response), \
         patch("wcm_worker.agents.visual_diff.screenshot_session") as mock_session:
        result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=15))

    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "Páginas WP destino en draft (404 público)"
    assert result.outputs["precheck_status_code"] == 404
    assert result.outputs["pages_compared"] == 0
    # NO debe abrir Playwright si el pre-check ya marca skip
    mock_session.assert_not_called()
    # Y debe haber añadido un ResidualTask (POST_GO_LIVE)
    fake_session.add.assert_called()
    residual = fake_session.add.call_args_list[0].args[0]
    assert "Publicar páginas" in residual.title


def test_precheck_5xx_devuelve_skip(fake_session) -> None:
    """Target devuelve 503 (server caído) → SKIPPED con razón explícita."""
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    fake_response = MagicMock()
    fake_response.status_code = 503

    with patch("wcm_worker.agents.visual_diff.httpx.get", return_value=fake_response), \
         patch("wcm_worker.agents.visual_diff.screenshot_session") as mock_session:
        result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=15))

    assert result.outputs["skipped"] is True
    assert "503" in result.outputs["reason"]
    mock_session.assert_not_called()


def test_precheck_request_error_devuelve_skip(fake_session) -> None:
    """Target inaccesible (DNS, network) → SKIPPED."""
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    with patch(
        "wcm_worker.agents.visual_diff.httpx.get",
        side_effect=httpx.ConnectError("nodename nor servname provided"),
    ), patch("wcm_worker.agents.visual_diff.screenshot_session") as mock_session:
        result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=15))

    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "Destino inaccesible"
    mock_session.assert_not_called()


def test_precheck_200_no_marca_skip_y_continua(fake_session) -> None:
    """Target responde 200 → no hay skip; el flujo intenta abrir Playwright."""
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    fake_response = MagicMock()
    fake_response.status_code = 200

    from wcm_worker.integrations.playwright_screenshot import PlaywrightNotAvailableError

    with patch("wcm_worker.agents.visual_diff.httpx.get", return_value=fake_response), \
         patch("wcm_worker.agents.visual_diff.screenshot_session") as mock_session:
        # No queremos correr Playwright real — forzamos error en el session.
        mock_session.side_effect = PlaywrightNotAvailableError("noop")
        result = VisualDiffAgent().run(AgentContext(session=fake_session, project_id=15))

    # El skipped llega por Playwright, NO por el pre-check
    assert result.outputs["skipped"] is True
    assert "Playwright" in result.summary
    mock_session.assert_called_once()


# ---------- D.2 timeout per-call ----------


def test_capture_acepta_timeout_ms_per_call() -> None:
    """playwright_screenshot.capture acepta timeout_ms para override per-call."""
    from wcm_worker.integrations.playwright_screenshot import ScreenshotSession

    fake_context = MagicMock()
    fake_page = MagicMock()
    fake_page.goto = MagicMock()
    fake_page.screenshot = MagicMock(return_value=b"PNGDATA")
    fake_context.new_page = MagicMock(return_value=fake_page)

    session = ScreenshotSession(
        playwright=MagicMock(),
        browser=MagicMock(),
        context=fake_context,
        viewport_width=1280,
        viewport_height=800,
        wait_until="networkidle",
        timeout_ms=30_000,
    )

    # Sin override → usa el timeout_ms de la sesión.
    session.capture("https://foo.com/")
    fake_page.goto.assert_called_with(
        "https://foo.com/", wait_until="networkidle", timeout=30_000
    )

    # Con override → usa el per-call.
    session.capture("https://foo.com/draft", timeout_ms=8_000)
    fake_page.goto.assert_called_with(
        "https://foo.com/draft", wait_until="networkidle", timeout=8_000
    )


def test_resolve_target_timeout_default() -> None:
    """Sin env → DEFAULT_TARGET_TIMEOUT_MS (8_000)."""
    agent = VisualDiffAgent()
    assert agent._resolve_target_timeout_ms() == DEFAULT_TARGET_TIMEOUT_MS


def test_resolve_target_timeout_env_override(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_TARGET_TIMEOUT_MS", "12000")
    assert VisualDiffAgent()._resolve_target_timeout_ms() == 12_000


def test_resolve_target_timeout_env_invalido_cae_a_default(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_TARGET_TIMEOUT_MS", "fast")
    assert VisualDiffAgent()._resolve_target_timeout_ms() == DEFAULT_TARGET_TIMEOUT_MS


def test_resolve_target_timeout_env_muy_bajo_se_descarta(monkeypatch) -> None:
    """Mínimo 1000ms — por debajo se ignora para evitar timeouts irreales."""
    monkeypatch.setenv("VISUAL_DIFF_TARGET_TIMEOUT_MS", "500")
    assert VisualDiffAgent()._resolve_target_timeout_ms() == DEFAULT_TARGET_TIMEOUT_MS


# ---------- D.3 cap fallos consecutivos ----------


def test_resolve_max_consecutive_failures_default() -> None:
    assert (
        VisualDiffAgent()._resolve_max_consecutive_failures()
        == DEFAULT_MAX_CONSECUTIVE_FAILURES
    )


def test_resolve_max_consecutive_failures_env_override(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES", "5")
    assert VisualDiffAgent()._resolve_max_consecutive_failures() == 5


@pytest.mark.parametrize("bad_value", ["abc", "0", "-1"])
def test_resolve_max_consecutive_failures_env_invalido(
    monkeypatch, bad_value: str
) -> None:
    monkeypatch.setenv("VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES", bad_value)
    assert (
        VisualDiffAgent()._resolve_max_consecutive_failures()
        == DEFAULT_MAX_CONSECUTIVE_FAILURES
    )


def test_consecutive_failures_residual_tiene_contenido() -> None:
    agent = VisualDiffAgent()
    project = _project_mock()
    residual = agent._consecutive_failures_residual(project, cap=3, remaining=47)
    assert "3 fallos consecutivos" in residual.title
    assert "47" in residual.description
    assert residual.generated_by == "visual-diff"


def test_draft_pages_residual_explica_publicar() -> None:
    agent = VisualDiffAgent()
    project = _project_mock()
    residual = agent._draft_pages_residual(project, "GET http://x → 404")
    assert "Publicar" in residual.title
    assert "draft" in residual.description.lower()
    assert "GET http://x → 404" in residual.description


# ---------- PrecheckResult dataclass ----------


def test_precheck_result_defaults() -> None:
    r = PrecheckResult()
    assert r.skip_reason is None
    assert r.detail == ""
    assert r.status_code is None


# ---------- D.4 WP_VERIFY_SSL ----------


@pytest.mark.parametrize(
    "env_value,expected_verify",
    [
        (None, True),       # default: verify SSL
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),   # dev con cert self-signed
        ("False", False),
        ("0", False),
        ("no", False),
    ],
)
def test_precheck_respeta_wp_verify_ssl(
    monkeypatch, env_value: str | None, expected_verify: bool, fake_session
) -> None:
    """El pre-check `httpx.get` debe usar `verify=WP_VERIFY_SSL`. En dev
    con cert auto-firmado (WP_VERIFY_SSL=false), sin esto el pre-check
    cae con SSLError y reporta falso "Destino inaccesible".
    """
    if env_value is None:
        monkeypatch.delenv("WP_VERIFY_SSL", raising=False)
    else:
        monkeypatch.setenv("WP_VERIFY_SSL", env_value)

    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: [_page_mock()]))
    fake_session.execute.return_value = res

    fake_response = MagicMock()
    fake_response.status_code = 200

    from wcm_worker.integrations.playwright_screenshot import PlaywrightNotAvailableError

    with patch(
        "wcm_worker.agents.visual_diff.httpx.get", return_value=fake_response
    ) as mock_get, patch(
        "wcm_worker.agents.visual_diff.screenshot_session"
    ) as mock_session:
        mock_session.side_effect = PlaywrightNotAvailableError("noop")
        VisualDiffAgent().run(AgentContext(session=fake_session, project_id=15))

    # Verificar que httpx.get fue llamado con verify=expected_verify
    assert mock_get.call_args.kwargs["verify"] is expected_verify
