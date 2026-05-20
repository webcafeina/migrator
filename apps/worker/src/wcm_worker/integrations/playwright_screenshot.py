"""Screenshots full-page con Playwright sync (v0.16.0).

Usado por `VisualDiffAgent` para capturar páginas origen + destino y
por `QaRunnerAgent` para validaciones que requieren render real.

Patrón sync (no async): el worker es Celery sync; abrir un loop asyncio
por screenshot infla complejidad. Playwright sync internamente usa el
mismo Chromium, solo cambia el wrapper.

`Playwright` y `chromium` se cargan lazy con try/except — si no están
instalados, lanzamos `PlaywrightNotAvailableError` para que el agent
caller marque la fase SKIPPED + cree residual task con instrucciones.

Resource sharing: `screenshot_session(viewport)` es un context manager
que arranca UN browser + UN context y permite tomar N screenshots
secuenciales reutilizando el mismo. Mucho más eficiente que un browser
por screenshot.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

log = logging.getLogger("wcm.worker.integrations.playwright_screenshot")

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
DEFAULT_WAIT_UNTIL = "networkidle"
DEFAULT_TIMEOUT_MS = 30_000


class PlaywrightNotAvailableError(RuntimeError):
    """Playwright no instalado o chromium no descargado. El agent
    caller debe capturar esto y degradar grácilmente."""


class ScreenshotSession:
    """Context para tomar varios screenshots reusando el mismo browser.

    Uso:
        with screenshot_session(viewport_width=1280) as session:
            png_origin = session.capture("https://barpepe.es/")
            png_target = session.capture("https://migrator.../")
    """

    def __init__(
        self,
        playwright: Any,
        browser: Any,
        context: Any,
        viewport_width: int,
        viewport_height: int,
        wait_until: str,
        timeout_ms: int,
    ) -> None:
        self._playwright = playwright
        self._browser = browser
        self._context = context
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._wait_until = wait_until
        self._timeout_ms = timeout_ms

    def capture(
        self,
        url: str,
        *,
        full_page: bool = True,
        timeout_ms: int | None = None,
    ) -> bytes:
        """Devuelve el PNG bytes de la captura.

        `timeout_ms` permite override per-call del timeout default de la
        sesión. Útil cuando una de las URLs es "probablemente caída"
        (p.ej. destino con páginas en draft) y se quiere fallar rápido
        en vez de esperar el timeout default — caso real: visual_diff
        contra 50 páginas draft consumía 25 min con timeout 30s.
        """
        page = self._context.new_page()
        try:
            page.goto(
                url,
                wait_until=self._wait_until,
                timeout=timeout_ms if timeout_ms is not None else self._timeout_ms,
            )
            return page.screenshot(full_page=full_page, type="png")
        finally:
            page.close()


@contextmanager
def screenshot_session(
    *,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    wait_until: str = DEFAULT_WAIT_UNTIL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> Iterator[ScreenshotSession]:
    """Abre browser + context. Cierra ambos al salir del with."""
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
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        try:
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=1,
                ignore_https_errors=True,
            )
            try:
                yield ScreenshotSession(
                    playwright=pw,
                    browser=browser,
                    context=context,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height,
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
        log.error("playwright_session_failed", extra={"error": str(e)})
        raise PlaywrightNotAvailableError(
            f"Browser chromium no disponible: {e}. Ejecuta `playwright install chromium`."
        ) from e
    finally:
        pw.stop()
