"""Wrapper sobre Playwright para renderizado dinámico.

Aísla las dependencias de Playwright bajo el extra `[browser]` para que
los tests unitarios sin Internet (la mayoría) no necesiten instalar
Chromium. Los tests browser se marcan con `@pytest.mark.browser` y se
skippean por defecto en CI ligero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

from wcm_scraper_core.proxy import ProxyConfig
from wcm_scraper_core.ua import UserAgentPool


@dataclass
class BrowserConfig:
    headless: bool = True
    viewport: dict[str, int] | None = None
    locale: str = "es-ES"
    timezone_id: str = "Europe/Madrid"
    timeout_ms: int = 30_000
    stealth: bool = True


class BrowserSession:
    """Context manager async sobre un BrowserContext de Playwright.

    Aplica anti-detección con `playwright-stealth` (opcional). Acepta un
    proxy por contexto. Para sticky session, mantener el mismo BrowserSession
    a lo largo del crawl de un dominio.

    Uso:
        async with BrowserSession(ua_pool=p) as bs:
            page = await bs.new_page("https://example.com")
            html = await page.content()

    Si Playwright no está instalado, lanza `RuntimeError` con mensaje
    accionable.
    """

    def __init__(
        self,
        *,
        ua_pool: UserAgentPool | None = None,
        proxy: ProxyConfig | None = None,
        config: BrowserConfig | None = None,
    ) -> None:
        self._ua_pool = ua_pool
        self._proxy = proxy
        self._config = config or BrowserConfig()
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> BrowserSession:
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:  # pragma: no cover — depende del extra opcional
            raise RuntimeError(
                "Playwright no instalado. Instala con: pip install '.[browser]' "
                "y luego: playwright install chromium"
            ) from e

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._config.headless,
        )

        context_kwargs: dict[str, Any] = {
            "viewport": self._config.viewport or {"width": 1366, "height": 900},
            "locale": self._config.locale,
            "timezone_id": self._config.timezone_id,
        }
        if self._ua_pool:
            context_kwargs["user_agent"] = self._ua_pool.next()
        if self._proxy:
            context_kwargs["proxy"] = {"server": self._proxy.url}

        self._context = await self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self._config.timeout_ms)

        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def new_page(self, url: str | None = None) -> Page:
        if self._context is None:  # pragma: no cover
            raise RuntimeError("BrowserSession no inicializada (usar con `async with`)")
        page = await self._context.new_page()

        if self._config.stealth:
            try:
                from playwright_stealth import stealth_async  # type: ignore[import-untyped]

                await stealth_async(page)
            except ImportError:  # pragma: no cover
                pass  # extra no instalado; degradación silenciosa

        if url is not None:
            await page.goto(url, wait_until="networkidle")
        return page

    async def screenshot_full_page(self, page: Page, path: str) -> None:
        await page.screenshot(path=path, full_page=True)
