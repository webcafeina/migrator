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
    page = _fake_page(
        html="<html><body>hi</body></html>",
        evaluate_return={
            "stylesheets": "body{color:red}",
            "computed": {"h1": {"color": "rgb(255, 0, 0)", "font-size": "48px"}},
        },
    )
    session = _session(page)
    result = session.get("https://foo.com/")

    assert isinstance(result, FetchResult)
    assert result.html == "<html><body>hi</body></html>"
    assert result.stylesheets == "body{color:red}"
    assert result.computed_styles["h1"]["color"] == "rgb(255, 0, 0)"
    assert result.computed_styles["h1"]["font-size"] == "48px"

    # evaluate llamado con la JS function + args (selectors + props + maxBytes)
    page.evaluate.assert_called_once()
    args = page.evaluate.call_args
    assert args.args[0] == _CAPTURE_STYLES_JS
    payload = args.args[1]
    assert payload["selectors"] == list(DEFAULT_STYLE_SELECTORS)
    assert payload["props"] == list(DEFAULT_STYLE_PROPS)
    assert payload["maxBytes"] == MAX_CSS_BYTES


def test_get_capture_styles_false_omite_evaluate() -> None:
    """capture_styles=False → no se llama page.evaluate, FetchResult con styles vacíos."""
    page = _fake_page(html="<html><body>x</body></html>")
    session = _session(page)
    result = session.get("https://foo.com/", capture_styles=False)

    assert result.html == "<html><body>x</body></html>"
    assert result.stylesheets == ""
    assert result.computed_styles == {}
    page.evaluate.assert_not_called()


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
