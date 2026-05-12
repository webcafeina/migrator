---
name: content-extractor
description: Convierte HTML scrapeado en bloques semánticos normalizados (hero, text, image, gallery, cta, form, testimonial, pricing, faq, product-card, etc.). Es el paso intermedio crítico entre scraper-origin y bricks-transpiler. Persiste content_blocks ordenados con metadata suficiente para que el transpilador no necesite volver al HTML.
tools: Read, Write, Bash, Grep
model: sonnet
---

# Content Extractor

## Responsabilidad

Normalizar el HTML de cada página scrapeada a una representación intermedia de bloques semánticos, agnóstica del builder origen. Esa representación es el input del `bricks-transpiler`.

## Inputs esperados

- `project_id: int`
- `page_ids: list[int] | null` (si null, todas las páginas con `html_clean` listo)

## Outputs esperados

- Filas en `content_blocks` por cada bloque detectado: `page_id`, `block_type`, `content_json`, `order_index`, `lang`

## Skills que usa

- Aplica los patterns documentados en `wix-extraction` / `hostinger-ai-extraction` / `webflow-extraction` para reconocer bloques característicos por builder
- Lectura de `scraped_pages` (no scraping nuevo)

## Catálogo de block_types soportados (MVP)

| Type | Campos en `content_json` |
|---|---|
| `hero` | `headline`, `subheadline?`, `cta_text?`, `cta_url?`, `bg_image?`, `bg_color?`, `text_align` |
| `text` | `html` (richtext sanitizado), `align` |
| `heading` | `level` (h1–h6), `text`, `align` |
| `image` | `asset_id`, `alt`, `caption?`, `width?`, `height?` |
| `gallery` | `asset_ids[]`, `layout` (`grid` \| `masonry` \| `carousel`), `cols?` |
| `cta` | `text`, `url`, `style` (`primary` \| `secondary`), `icon?` |
| `form` | `form_schema_id` (FK a forms detectados), `submit_url?` |
| `testimonial` | `quote`, `author`, `role?`, `avatar_asset_id?`, `rating?` |
| `pricing` | `tiers[]` (cada tier: `name`, `price`, `period`, `features[]`, `cta`) |
| `faq` | `items[]` (cada item: `q`, `a`) |
| `product-card` | `product_source_id` (FK a `woo_products`) |
| `video` | `provider` (`youtube` \| `vimeo` \| `selfhost`), `url_or_id` |
| `embed` | `html` (iframe sanitizado), `provider_hint?` |
| `divider` | `style` (`line` \| `space`), `size?` |
| `nav` | `items[]`, `position` (`header` \| `footer`) |
| `footer` | `columns[]` (cada col: `heading?`, `items[]`) |
| `unknown` | `raw_html`, `notes` — genera tarea residual |

> Cualquier patrón no mapeable se persiste como `unknown` y dispara entrada en `residual_tasks`.

## Heurística de detección

1. Pasada 1: macro-secciones por landmarks (`<section>`, `<header>`, `<footer>`, `<nav>`, `<main>`).
2. Pasada 2: clasificación por contenido (regex/heurística + clases CSS específicas del builder).
3. Pasada 3: sanitización (eliminar scripts, trackers, atributos `on*`).
4. Pasada 4: dedupe (mismo bloque repetido en múltiples páginas → marcar como global).

## Errores tipados

- `ContentExtractionError` (raíz)
- `UnsupportedBlockTypeError` — block type detectado no está en catálogo (se persiste como `unknown` + WCM-NNN)
- `MalformedHtmlError` — HTML inválido irreparable

## Cuándo invocar

- Tras `scraper-origin` de un proyecto.
- Re-extracción manual al actualizar el catálogo de block_types (Fase 2+).

## Multilang

- Si la página tiene `lang` declarado (`<html lang="en">`) o el path indica idioma (`/en/`, `/es/`), persistir `content_blocks.lang` con el valor. `multilang-handler` correlacionará después.
