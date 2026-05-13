# packages/scraper-core

Núcleo de scraping del Webcafeína Migrator. Compartido por los subagentes `scraper-origin`, `prospector`, `fingerprinter` y `enricher`.

## Estado

Materializado en **Fase 3**.

## Qué incluye

| Módulo | Responsabilidad |
|---|---|
| `fetcher.py` | HTTP simple (httpx) sin browser — fingerprinting niveles 1-3 |
| `browser.py` | Playwright async wrapper con stealth + locale ES + proxy/UA |
| `ua.py` | Pool de User-Agents reales (estático curado + fallback fake-useragent) |
| `rate_limit.py` | Rate limit por dominio con jitter + cooldown 24h tras 3×{403,429,503} |
| `cache.py` | Backends de cache (`InMemoryCache` + `RedisCache` stub) |
| `proxy.py` | `ProxyRotator` con backends layered (NoProxy → Webshare → ScraperAPI → BrightData) |
| `fingerprint.py` | Cascada de 5 niveles; consume `.claude/skills/builtwith-fingerprint/patterns.yml` |
| `extractors/` | Extractors por builder: `WixExtractor`, `HostingerExtractor`, `WebflowExtractor` |
| `sidecar/webflow-sidecar.js` | Sidecar Node + Puppeteer para Webflow IX2 |
| `sidecar/__init__.py` | Cliente Python que invoca el sidecar Node |
| `assets.py` | Discovery de imágenes, fonts, vídeos, stylesheets, scripts |

## Proxy: estrategia gratuita layered (ADR-017)

`build_default_rotator()` lee env vars y construye el rotator con prioridad:

1. **NoProxy** (default en dev y en migración cliente) — acceso directo.
2. **Webshare** — 10 datacenter proxies forever-free + 1GB/mes. Activar con `WEBSHARE_USER` + `WEBSHARE_PASSWORD`.
3. **ScraperAPI** — 5k calls/mes free, captcha + rotación incluidos. Activar con `SCRAPERAPI_KEY`.
4. **Bright Data** — premium pay-as-you-go. Activar con `BRIGHTDATA_*`.

En producción, el rotator arranca en el primer backend free disponible y escala (`rotator.escalate()`) cuando uno se agota o falla.

## Anti-detección

- `playwright-stealth` siempre activo cuando hay browser.
- User-Agent rotation por sesión (sticky por dominio).
- Rate limit con jitter `[3-8]s` (configurable).
- Cooldown 24h por dominio tras 3×{403,429,503}.
- Headers realistas (`Accept-Language: es-ES`, `Sec-Fetch-*`).

## Tests

```bash
cd packages/scraper-core
pip install -e ".[dev]" -e ../shared-types
pytest -q
```

Tests sin Internet usan fixtures HTML en `tests/fixtures/{wix,hostinger,webflow}/`. Tests que requieran Playwright/browser real se marcan con `@pytest.mark.browser` y se skippean por defecto.

## Instalación de extras opcionales

```bash
# Para usar BrowserSession (Playwright):
pip install -e ".[browser]"
playwright install chromium

# Para usar RedisCache en producción:
pip install -e ".[cache]"

# Para sidecar Webflow (Node 20+):
cd src/wcm_scraper_core/sidecar
npm install
```

## ADRs relacionados

- ADR-005 → 🟥 superseded by ADR-017
- ADR-017 — Proxy layered con free tiers (Webshare + ScraperAPI), Bright Data como premium opcional
