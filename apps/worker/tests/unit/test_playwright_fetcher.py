"""Tests C.1 (2026-05-21) — FetchSession devuelve FetchResult con CSS + computed styles.

Mockea el `context.new_page()` para no requerir Playwright real en CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from wcm_worker.integrations.playwright_fetcher import (
    _CAPTURE_STYLES_JS,
    DEFAULT_STYLE_PROPS,
    DEFAULT_STYLE_SELECTORS,
    MAX_CSS_BYTES,
    FetchResult,
    FetchSession,
)


def _fake_page(
    *,
    html: str = "<html><body>x</body></html>",
    evaluate_return: dict | None = None,
    evaluate_raises: Exception | None = None,
) -> MagicMock:
    page = MagicMock()
    page.goto = MagicMock()
    page.content = MagicMock(return_value=html)
    if evaluate_raises is not None:
        page.evaluate = MagicMock(side_effect=evaluate_raises)
    else:
        page.evaluate = MagicMock(return_value=evaluate_return or {})
    page.close = MagicMock()
    return page


def _fake_context(page: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.new_page = MagicMock(return_value=page)
    return ctx


def _session(page: MagicMock, **kwargs) -> FetchSession:
    return FetchSession(
        context=_fake_context(page),
        wait_until="domcontentloaded",
        timeout_ms=30_000,
        **kwargs,
    )


# ---------- FetchResult ----------


def test_fetch_result_defaults() -> None:
    r = FetchResult(html="<x/>")
    assert r.html == "<x/>"
    assert r.stylesheets == ""
    assert r.computed_styles == {}


# ---------- get() con captura de styles ----------


def test_get_devuelve_html_y_styles_por_default() -> None:
    """AI.1 — `get()` ahora hace 2 evaluates (styles + detect sections)
    + page.screenshot(). El mock devuelve el mismo `evaluate_return`
    para ambos; solo verificamos el primer call con CAPTURE_STYLES_JS.
    """
    page = _fake_page(
        html="<html><body>hi</body></html>",
        evaluate_return={
            "stylesheets": "body{color:red}",
            "computed": {"h1": {"color": "rgb(255, 0, 0)", "font-size": "48px"}},
        },
    )
    session = _session(page)
    result = session.get("https://foo.com/", capture_screenshots=False)

    assert isinstance(result, FetchResult)
    assert result.html == "<html><body>hi</body></html>"
    assert result.stylesheets == "body{color:red}"
    assert result.computed_styles["h1"]["color"] == "rgb(255, 0, 0)"
    assert result.computed_styles["h1"]["font-size"] == "48px"

    # evaluate llamado al menos 1 vez con CAPTURE_STYLES_JS.
    assert page.evaluate.call_count == 1
    args = page.evaluate.call_args_list[0]
    assert args.args[0] == _CAPTURE_STYLES_JS
    payload = args.args[1]
    assert payload["selectors"] == list(DEFAULT_STYLE_SELECTORS)
    assert payload["props"] == list(DEFAULT_STYLE_PROPS)
    assert payload["maxBytes"] == MAX_CSS_BYTES


def test_get_capture_styles_false_omite_styles_evaluate() -> None:
    """capture_styles=False + capture_screenshots=False → 0 evaluates."""
    page = _fake_page(html="<html><body>x</body></html>")
    session = _session(page)
    result = session.get(
        "https://foo.com/", capture_styles=False, capture_screenshots=False
    )

    assert result.html == "<html><body>x</body></html>"
    assert result.stylesheets == ""
    assert result.computed_styles == {}
    assert result.full_page_png is None
    assert result.section_bboxes == []
    page.evaluate.assert_not_called()
    page.screenshot.assert_not_called()


def test_get_captura_screenshot_y_bboxes_por_default() -> None:
    """AI.1 — Default emite full_page_png + section_bboxes."""
    fake_bboxes = [
        {"idx": 0, "selector": "#comp-1", "bbox": {"x": 0, "y": 0, "w": 100, "h": 50}},
        {"idx": 1, "selector": "#comp-2", "bbox": {"x": 0, "y": 50, "w": 100, "h": 80}},
    ]
    page = _fake_page(html="<html><body>x</body></html>")
    # 1ª evaluate = styles, 2ª = detect sections.
    page.evaluate = MagicMock(
        side_effect=[
            {"stylesheets": "", "computed": {}},
            fake_bboxes,
        ]
    )
    page.screenshot = MagicMock(return_value=b"FAKE_PNG_BYTES")
    session = _session(page)
    result = session.get("https://foo.com/")

    assert result.full_page_png == b"FAKE_PNG_BYTES"
    assert result.section_bboxes == fake_bboxes
    # screenshot llamado con full_page=True
    page.screenshot.assert_called_once()
    kwargs = page.screenshot.call_args.kwargs
    assert kwargs.get("full_page") is True
    assert kwargs.get("type") == "png"


def test_get_screenshot_falla_no_rompe_fetch() -> None:
    """Si page.screenshot levanta excepción, full_page_png queda None
    pero html y styles se devuelven igual (graceful degradation)."""
    page = _fake_page(html="<html><body>x</body></html>")
    page.evaluate = MagicMock(return_value={"stylesheets": "", "computed": {}})
    page.screenshot = MagicMock(side_effect=RuntimeError("page closed"))
    session = _session(page)
    result = session.get("https://foo.com/")

    assert result.html == "<html><body>x</body></html>"
    assert result.full_page_png is None


def test_get_evaluate_falla_no_rompe_fetch() -> None:
    """Si page.evaluate levanta excepción (raro, p.ej. CORS edge), el
    fetch devuelve HTML pero con styles vacíos — graceful degradation."""
    page = _fake_page(
        html="<html><body>x</body></html>",
        evaluate_raises=RuntimeError("CSP blocked evaluate"),
    )
    session = _session(page)
    result = session.get("https://foo.com/")

    assert result.html == "<html><body>x</body></html>"
    assert result.stylesheets == ""
    assert result.computed_styles == {}


def test_get_evaluate_devuelve_null_no_crashea() -> None:
    """Si el JS devuelve {} sin las keys esperadas (page sin styles), no crashea."""
    page = _fake_page(
        html="<html></html>",
        evaluate_return={"stylesheets": None, "computed": None},
    )
    session = _session(page)
    result = session.get("https://foo.com/")

    assert result.stylesheets == ""
    assert result.computed_styles == {}


def test_get_cierra_page_aunque_falle() -> None:
    """page.close() siempre se invoca (try/finally)."""
    page = _fake_page()
    page.goto.side_effect = RuntimeError("goto timeout")
    session = _session(page)

    try:
        session.get("https://foo.com/")
    except RuntimeError:
        pass

    page.close.assert_called_once()
