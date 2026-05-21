"""PlaywrightFetcher — helper async para descargar HTML renderizado (ADR-040, v0.20.0+).

Reutiliza browser + context entre múltiples páginas (resource sharing).
Pensado para `scraper_origin` y futuros agents que necesiten HTML
hidratado (Wix/Webflow/SPA en general).

C.1 (2026-05-21): además del HTML, captura CSS de stylesheets
same-origin y computed styles de selectores clave (body, h1-h6, p,
a, button, .wixui-*). El extractor y `theme_styles` los usan para
sintetizar el Theme Styles del proyecto destino.

NO confundir con `playwright_screenshot.py` — éste devuelve HTML, aquél
PNG. Comparten el mismo wrapper de instalación; si `playwright` no está
instalado se lanza `PlaywrightNotAvailableError` (importada de allí).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from wcm_worker.integrations.playwright_screenshot import (
    PlaywrightNotAvailableError,
)

log = logging.getLogger("wcm.worker.playwright_fetcher")

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
# `domcontentloaded` en lugar de `networkidle`: muchas webs modernas tienen
# trackers/analytics/heartbeats que mantienen actividad de red constante y
# nunca alcanzan "sin tráfico durante 500ms". Con `domcontentloaded`
# tenemos el HTML hidratado tras el DOMContentLoaded, suficiente para
# extracción. Override por env WCM_PW_WAIT_UNTIL si se necesita esperar
# más (p.ej. "load" o "networkidle" para sites simples sin trackers).
DEFAULT_WAIT_UNTIL = "domcontentloaded"
DEFAULT_TIMEOUT_MS = 30_000

#: Selectores que capturamos vía getComputedStyle. Son los elementos
#: tipográficos y de UI básicos que necesita `theme_styles` para
#: sintetizar la paleta y la tipografía del proyecto destino.
DEFAULT_STYLE_SELECTORS = (
    "body", "h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "button",
    ".wixui-button", ".wixui-rich-text",
)

#: Props que extraemos de cada elemento. Limitado para no inflar el
#: JSON (Wix tiene cientos de computed props por elemento).
DEFAULT_STYLE_PROPS = (
    "color", "background-color", "font-family", "font-size",
    "font-weight", "line-height", "padding", "margin", "text-align",
)

#: Cuánto CSS guardamos como máximo. Wix puede meter MB de CSS via
#: `<style>` inline; truncamos a 256 KB para mantener `scraped_pages`
#: razonable. El theme styles solo necesita una muestra.
MAX_CSS_BYTES = 256 * 1024


@dataclass
class FetchResult:
    """Resultado de `FetchSession.get`. C.1.

    - `html`: el `page.content()` tras la hidratación.
    - `stylesheets`: concatenación del CSS inline + stylesheets
      same-origin accesibles (truncado a MAX_CSS_BYTES).
    - `computed_styles`: dict `selector → {prop → value}` con los
      DEFAULT_STYLE_PROPS evaluados por `getComputedStyle()` en el
      browser. Vacío para selectores no presentes en el DOM.
    """

    html: str
    stylesheets: str = ""
    computed_styles: dict[str, dict[str, str]] = field(default_factory=dict)


#: JavaScript que se ejecuta en el browser (vía page.evaluate). Devuelve
#: `{stylesheets: str, computed: {selector: {prop: value}}}`. El bloque
#: try/catch alrededor de cssRules es necesario porque los stylesheets
#: cross-origin (CDN Wix, fonts.googleapis) levantan SecurityError al
#: leer cssRules — los saltamos limpiamente.
_CAPTURE_STYLES_JS = """
(args) => {
    const { selectors, props, maxBytes } = args;
    // 1) CSS: <style> inline + stylesheets same-origin accesibles.
    let css = '';
    for (const sheet of Array.from(document.styleSheets)) {
        try {
            const rules = sheet.cssRules || [];
            for (const rule of Array.from(rules)) {
                css += rule.cssText + '\\n';
                if (css.length >= maxBytes) break;
            }
        } catch (e) {
            // Cross-origin stylesheet — skip silently.
        }
        if (css.length >= maxBytes) break;
    }
    if (css.length > maxBytes) css = css.slice(0, maxBytes);

    // 2) Computed styles de selectores clave.
    const computed = {};
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (!el) continue;
        const style = window.getComputedStyle(el);
        const out = {};
        for (const p of props) {
            const v = style.getPropertyValue(p);
            if (v) out[p] = v;
        }
        computed[sel] = out;
    }
    return { stylesheets: css, computed: computed };
}
"""


class FetchSession:
    """Sesión de scraping con browser+context reutilizables.

    Uso:
        with fetcher_session() as fetch:
            r = fetch.get("https://barpepe.es/")
            html = r.html
            css = r.stylesheets
            comp = r.computed_styles  # {"h1": {"color": "rgb(0,0,0)", ...}, ...}
    """

    def __init__(
        self,
        context: Any,
        wait_until: str,
        timeout_ms: int,
    ) -> None:
        self._context = context
        self._wait_until = wait_until
        self._timeout_ms = timeout_ms

    def get(self, url: str, *, capture_styles: bool = True) -> FetchResult:
        """Carga `url` con Playwright y devuelve FetchResult con HTML
        y opcionalmente CSS + computed styles. C.1.

        Si `capture_styles=False`, omite el page.evaluate (más rápido
        pero pierde info para theme_styles). Default `True` porque el
        único caller productivo (scraper_origin) los quiere.

        Levanta `PlaywrightFetchError` (descendiente de RuntimeError) si
        el navegador falla en goto — el caller decide si reintentar o
        marcar la página como FAILED.
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until=self._wait_until, timeout=self._timeout_ms)
            html = page.content()
            stylesheets = ""
            computed: dict[str, dict[str, str]] = {}
            if capture_styles:
                try:
                    styles_data = page.evaluate(
                        _CAPTURE_STYLES_JS,
                        {
                            "selectors": list(DEFAULT_STYLE_SELECTORS),
                            "props": list(DEFAULT_STYLE_PROPS),
                            "maxBytes": MAX_CSS_BYTES,
                        },
                    )
                    stylesheets = styles_data.get("stylesheets", "") or ""
                    computed = styles_data.get("computed", {}) or {}
                except Exception as e:  # noqa: BLE001 — evaluate puede fallar
                    log.warning(
                        "playwright_capture_styles_failed",
                        extra={"url": url, "error": str(e)[:200]},
                    )
            return FetchResult(
                html=html, stylesheets=stylesheets, computed_styles=computed
            )
        finally:
            page.close()


class PlaywrightFetchError(RuntimeError):
    """Wraps cualquier fallo Playwright durante fetch (timeout, DNS,
    blocking page). El caller decide si retry o failed_page."""


@contextmanager
def fetcher_session(
    *,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    wait_until: str = DEFAULT_WAIT_UNTIL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    user_agent: str = "WebcafeinaMigrator/0.1 (Authorized migration)",
) -> Iterator[FetchSession]:
    """Abre browser+context Playwright. Cierra todo al salir del with."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PlaywrightNotAvailableError(
            "Playwright no instalado. `pip install 'playwright>=1.45'` "
            "+ `playwright install chromium` (+ `playwright install-deps` en Linux)."
        ) from e

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=1,
                ignore_https_errors=True,
                user_agent=user_agent,
            )
            try:
                yield FetchSession(
                    context=context,
                    wait_until=wait_until,
                    timeout_ms=timeout_ms,
                )
            finally:
                context.close()
        finally:
            browser.close()
    except PlaywrightNotAvailableError:
        raise
    except Exception as e:
        log.error("playwright_fetcher_session_failed", extra={"error": str(e)})
        raise PlaywrightNotAvailableError(
            f"Browser chromium no disponible: {e}. "
            "Ejecuta `playwright install chromium`."
        ) from e
    finally:
        pw.stop()
