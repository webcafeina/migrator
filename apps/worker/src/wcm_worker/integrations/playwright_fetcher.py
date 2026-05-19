"""PlaywrightFetcher — helper async para descargar HTML renderizado (ADR-040, v0.20.0+).

Reutiliza browser + context entre múltiples páginas (resource sharing).
Pensado para `scraper_origin` y futuros agents que necesiten HTML
hidratado (Wix/Webflow/SPA en general).

NO confundir con `playwright_screenshot.py` — éste devuelve HTML, aquél
PNG. Comparten el mismo wrapper de instalación; si `playwright` no está
instalado se lanza `PlaywrightNotAvailableError` (importada de allí).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from wcm_worker.integrations.playwright_screenshot import (
    PlaywrightNotAvailableError,
)

log = logging.getLogger("wcm.worker.playwright_fetcher")

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
DEFAULT_WAIT_UNTIL = "networkidle"
DEFAULT_TIMEOUT_MS = 30_000


class FetchSession:
    """Sesión de scraping con browser+context reutilizables.

    Uso:
        with fetcher_session() as fetch:
            html_home = fetch.get("https://barpepe.es/")
            html_about = fetch.get("https://barpepe.es/sobre-nosotros")
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

    def get(self, url: str) -> str:
        """Carga `url` con Playwright (espera hidratación) y devuelve el HTML.

        Levanta `PlaywrightFetchError` (descendiente de RuntimeError) si
        el navegador falla en goto — el caller decide si reintentar o
        marcar la página como FAILED.
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until=self._wait_until, timeout=self._timeout_ms)
            return page.content()
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
