"""Webcafeína Migrator — scraper core.

Exporta los componentes principales:
- Fetcher HTTP simple (sin browser) para fingerprinting nivel 1-3.
- BrowserSession (Playwright) para renderizado dinámico (niveles 4-5,
  scraper-origin de migración).
- ProxyRotator con backends layered (NoProxy → Webshare → ScraperAPI → BrightData).
- UserAgentPool con rotación.
- DomainRateLimiter con jitter + cooldown.
- Fingerprinter (cascada 5 niveles).
- Extractors por builder.
- Asset discovery.
"""

from wcm_scraper_core.assets import AssetRef, discover_assets
from wcm_scraper_core.cache import CacheBackend, InMemoryCache
from wcm_scraper_core.extractors import (
    BuilderExtractor,
    ExtractionResult,
    HostingerExtractor,
    WebflowExtractor,
    WixExtractor,
    get_extractor,
)
from wcm_scraper_core.fetcher import FetchResult, fetch_html
from wcm_scraper_core.fingerprint import (
    FingerprintResult,
    TechMatch,
    fingerprint_url,
)
from wcm_scraper_core.proxy import ProxyConfig, ProxyRotator, build_default_rotator
from wcm_scraper_core.rate_limit import DomainRateLimiter
from wcm_scraper_core.ua import UserAgentPool

__all__ = [
    "AssetRef",
    "BuilderExtractor",
    "CacheBackend",
    "DomainRateLimiter",
    "ExtractionResult",
    "FetchResult",
    "FingerprintResult",
    "HostingerExtractor",
    "InMemoryCache",
    "ProxyConfig",
    "ProxyRotator",
    "TechMatch",
    "UserAgentPool",
    "WebflowExtractor",
    "WixExtractor",
    "build_default_rotator",
    "discover_assets",
    "fetch_html",
    "fingerprint_url",
    "get_extractor",
]
