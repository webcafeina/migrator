"""Fetcher HTTP simple (sin browser).

Para fingerprinting de nivel 1-3 (headers + HTML markers + recursos) no
necesitamos renderizado. Un fetcher ligero con httpx es 50× más barato que
arrancar Playwright.

Para renderizado dinámico (Wix/Hostinger/Webflow extractors) usar
`browser.BrowserSession` (Playwright). Este fetcher es para
fingerprinter y crawl ligero.
"""

from __future__ import annotations

from dataclasses import dataclass

from wcm_scraper_core.proxy import ProxyConfig, ProxyRotator
from wcm_scraper_core.rate_limit import DomainRateLimiter
from wcm_scraper_core.ua import UserAgentPool


@dataclass
class FetchResult:
    url: str
    final_url: str  # tras redirects
    status_code: int
    headers: dict[str, str]
    html: str
    response_time_ms: float
    proxy_used: str | None
    user_agent: str
    cached: bool = False


async def fetch_html(
    url: str,
    *,
    rotator: ProxyRotator | None = None,
    ua_pool: UserAgentPool | None = None,
    rate_limiter: DomainRateLimiter | None = None,
    sticky_key: str | None = None,
    timeout_s: float = 30.0,
    follow_redirects: bool = True,
    respect_robots: bool = False,
) -> FetchResult:
    """Descarga HTML de una URL con anti-detección.

    Importa httpx perezosamente para que el paquete instale sin la
    dependencia HTTP cuando solo se use offline en tests.

    `respect_robots=True` se aplica en prospección. En migración (web del
    cliente con consentimiento) se ignora.
    """
    import time

    import httpx

    ua = ua_pool.for_session(sticky_key) if (ua_pool and sticky_key) else (
        ua_pool.next() if ua_pool else "Mozilla/5.0"
    )
    proxy_cfg: ProxyConfig | None = (
        rotator.next_proxy(sticky_key=sticky_key) if rotator else None
    )

    if rate_limiter:
        await rate_limiter.acquire(url)

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, br, deflate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    proxies = proxy_cfg.url if proxy_cfg else None
    client_kwargs: dict[str, object] = {
        "timeout": timeout_s,
        "follow_redirects": follow_redirects,
        "headers": headers,
    }
    if proxies:
        client_kwargs["proxy"] = proxies

    start = time.perf_counter()
    async with httpx.AsyncClient(**client_kwargs) as client:
        response = await client.get(url)
    elapsed_ms = (time.perf_counter() - start) * 1000

    if rate_limiter and response.status_code in (403, 429, 503):
        rate_limiter.report_blocked(url, response.status_code)

    return FetchResult(
        url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        headers=dict(response.headers),
        html=response.text,
        response_time_ms=elapsed_ms,
        proxy_used=proxy_cfg.label if proxy_cfg else None,
        user_agent=ua,
        cached=False,
    )
