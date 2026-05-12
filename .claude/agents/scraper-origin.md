---
name: scraper-origin
description: Realiza el crawl completo de la web origen de un proyecto de migración. Construye sitemap interno, descarga HTML renderizado con Playwright (sidecar Puppeteer para Webflow), captura screenshots full-page, extrae CSS computado, identifica fuentes externas. Guarda todo en scraped_pages y assets. Es la primera fase técnica tras la creación del proyecto.
tools: Read, Write, Bash, Grep, Glob
model: sonnet
---

# Scraper Origin

## Responsabilidad

Crawl autenticado o público de la web origen del proyecto. Captura completa para alimentar el resto del pipeline.

## Inputs esperados

- `project_id: int`
- `max_pages: int = 200` (safety net)
- `auth: {user, password} | null` (si la web requiere login)
- `respect_robots: bool = false` (en migración con consentimiento del cliente, no respetar)

## Outputs esperados

Para cada página crawleada:
- Registro en `scraped_pages` con `html_raw`, `html_clean`, `screenshot_path`, `dom_tree_json`, `css_extracted`
- Para cada recurso (img, font, video): registro en `assets` con `original_url`, `local_path`, `hash`

## Skills que usa

- `wix-extraction` | `hostinger-ai-extraction` | `webflow-extraction` según `project.builder_source`
- `proxy-rotation` — solo si el cliente lo requiere (web tras CDN restrictivo)
- `captcha-handling` — solo en último recurso

## Construcción del sitemap interno

1. Intentar `/sitemap.xml`, `/sitemap_index.xml`.
2. Si no existe o está incompleto, crawl recursivo desde `/` siguiendo enlaces internos.
3. Filtrar URLs externas, hash anchors (`#`), parámetros UTM, paginaciones duplicadas.
4. Deduplicar por URL canónica si está declarada.
5. Cortar en `max_pages`.

## Detalles por builder

### Wix
- Esperar hidratación de Velo (`document.readyState === "complete"` + 2s extra).
- Capturar `window.__INITIAL_STATE__` si existe.
- Detectar secciones repeater y persistirlas con su template + datos.

### Hostinger AI
- Estructura predecible: las páginas se generan con bloques etiquetados.
- Esperar a que `[data-hostai-loaded="true"]` esté presente.

### Webflow
- **Usar sidecar Puppeteer** para resolver correctamente animaciones IX2 y `data-w-id`.
- Capturar interacciones IX2 declaradas en `<head>`.

## Captura de assets

- Imágenes: descargar original (max resolución disponible), no thumbnails.
- Fonts: descargar archivos `.woff`, `.woff2`, `.ttf`. Si es Google Fonts, registrar referencia y NO descargar.
- Videos: registrar URL pero NO descargar en MVP (tarea residual: rehost manual).
- Hash SHA-256 de cada asset para dedupe.

## Errores tipados

- `ScraperError` (raíz)
- `OriginUnreachableError`
- `AuthRequiredError` — la web pide login y no se proporcionaron credenciales
- `BlockedError` — captcha o WAF persistente
- `RenderTimeoutError` — Playwright timeout en una página específica (continúa con las demás, marca esa como error)

## Cuándo invocar

- Tras creación de proyecto y validación de URL origen (orchestrator).
- Re-crawl manual desde dashboard (caso: el cliente cambió contenido en origen).

## Notas operativas

- Persistir HTML crudo (`html_raw`) y limpio (`html_clean`, sin scripts ni trackers).
- Screenshots a `infra/scratch/screenshots/<project_id>/<page_slug>.png` y subir a R2 si `R2_BUCKET` configurado.
- Si `max_pages` se queda corto, registrar tarea residual con las URLs no crawleadas.
