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
    """Resultado de `FetchSession.get`. C.1 + AI.1.

    - `html`: el `page.content()` tras la hidratación.
    - `stylesheets`: concatenación del CSS inline + stylesheets
      same-origin accesibles (truncado a MAX_CSS_BYTES).
    - `computed_styles`: dict `selector → {prop → value}` con los
      DEFAULT_STYLE_PROPS evaluados por `getComputedStyle()` en el
      browser. Vacío para selectores no presentes en el DOM.
    - `full_page_png` (AI.1): bytes PNG del screenshot full-page. None
      si `capture_screenshots=False` o si la captura falla.
    - `section_bboxes` (AI.1): lista `[{idx, selector, bbox}]` con la
      posición/tamaño de cada sección top-level del origen. Usado por
      scraper_origin para recortar el full_page_png en sub-PNGs y
      subirlos a R2 con clave `wcm/projects/{pid}/sections/{page_id}/{idx}.png`.
    """

    html: str
    stylesheets: str = ""
    computed_styles: dict[str, dict[str, str]] = field(default_factory=dict)
    full_page_png: bytes | None = None
    section_bboxes: list[dict[str, Any]] = field(default_factory=list)


#: AI.1 — Selectores de secciones top-level del origen. Coinciden con
#: los que `wcm_scraper_core.extractors.wix.WixExtractor` usa para
#: iterar (data-mesh-id para Wix Studio, section id^="comp-" para
#: Editor clásico). Mantener sincronizado.
_SECTION_SELECTOR = 'section[data-mesh-id], section[id^="comp-"]'

#: AI.1 — JS que detecta secciones y devuelve sus bounding boxes en
#: coordenadas DEL DOCUMENTO (incluyendo scroll). Eso permite recortar
#: el screenshot full-page de Playwright sin recalcular posiciones.
_DETECT_SECTIONS_JS = f"""
() => {{
    const sections = Array.from(document.querySelectorAll('{_SECTION_SELECTOR}'));
    return sections.map((s, idx) => {{
        const r = s.getBoundingClientRect();
        let selector;
        if (s.id) selector = '#' + s.id;
        else if (s.getAttribute('data-mesh-id')) {{
            selector = `[data-mesh-id="${{s.getAttribute('data-mesh-id')}}"]`;
        }} else selector = `section:nth-of-type(${{idx + 1}})`;
        return {{
            idx: idx,
            selector: selector,
            bbox: {{
                x: r.x + window.scrollX,
                y: r.y + window.scrollY,
                w: r.width,
                h: r.height,
            }},
        }};
    }}).filter(s => s.bbox.w > 0 && s.bbox.h > 0);
}}
"""

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

    def get(
        self,
        url: str,
        *,
        capture_styles: bool = True,
        capture_screenshots: bool = True,
    ) -> FetchResult:
        """Carga `url` con Playwright y devuelve FetchResult con HTML
        y opcionalmente CSS + computed styles + full-page PNG + bboxes
        de secciones. C.1 + AI.1.

        - `capture_styles=False`: omite el evaluate de CSS (más rápido,
          pierde info para theme_styles).
        - `capture_screenshots=False`: omite el screenshot full-page +
          bboxes (más rápido, sin material para ai_assist).

        Default ambos `True` porque el único caller productivo
        (scraper_origin) los quiere.

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
            full_page_png: bytes | None = None
            section_bboxes: list[dict[str, Any]] = []

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

            # AI.1 — Capturar full-page screenshot + bboxes de secciones.
            # Separados del CSS capture para que un fallo en uno no
            # arrastre al otro.
            if capture_screenshots:
                try:
                    section_bboxes = page.evaluate(_DETECT_SECTIONS_JS) or []
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "playwright_detect_sections_failed",
                        extra={"url": url, "error": str(e)[:200]},
                    )
                    section_bboxes = []
                try:
                    full_page_png = page.screenshot(
                        full_page=True, type="png", timeout=self._timeout_ms
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "playwright_screenshot_failed",
                        extra={"url": url, "error": str(e)[:200]},
                    )
                    full_page_png = None

            return FetchResult(
                html=html,
                stylesheets=stylesheets,
                computed_styles=computed,
                full_page_png=full_page_png,
                section_bboxes=section_bboxes,
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
