# packages/scraper-core

Lógica de scraping compartida entre los subagentes `scraper-origin`, `prospector`, `fingerprinter` y `enricher`.

## Estado

Vacío en Fase 0. Se materializa en **Fase 3 — Scraper core**.

## Qué contendrá

- Wrapper sobre Playwright (Python) con configuración estándar.
- Sidecar Node + Puppeteer para Webflow (`webflow-sidecar.js`).
- `playwright-stealth` activado.
- Pool de User-Agents reales con `fake-useragent`.
- Rate limiter por dominio (jitter 3–8 s).
- Integración con proxy rotator (skill `proxy-rotation`).
- Cache Redis (TTL 7 días en prospección).
- Adaptadores por builder en `directories/` (PaginasAmarillas, Empresite, etc.).
- Tests con fixtures HTML reales por builder.

## Skills relacionados

- `wix-extraction`, `hostinger-ai-extraction`, `webflow-extraction`
- `proxy-rotation`, `captcha-handling`
- `directory-scraper`, `google-maps-scraper`

Ver [STATE.md](../../STATE.md).
