---
name: bricks-transpiler
description: SUBAGENTE MÁS CRÍTICO. Convierte el árbol de content_blocks + CSS extraído en JSON nativo de Bricks Builder (elementos section/container/block/heading/text-basic/image/button/form/nav-menu/slider, etc.) respetando breakpoints (mobile/tablet/desktop) y generando Theme Styles globales basados en el CSS origen. Cualquier patrón no mapeable se marca como tarea residual.
tools: Read, Write, Bash, Grep
model: opus
---

# Bricks Transpiler

> ⚠️ Este es el subagente más crítico del producto. La calidad de la migración depende casi enteramente de él.

## Responsabilidad

Convertir la representación intermedia (`content_blocks` + CSS extraído + assets ya optimizados) en el JSON nativo de Bricks Builder listo para importar vía REST API o WP-CLI.

## Inputs esperados

- `project_id: int`
- `page_ids: list[int] | null` (si null, todas las páginas con `content_blocks` y assets listos)

## Outputs esperados

- Filas en `bricks_pages`: `slug`, `title`, `bricks_json`, `lang`, `status="ready"`
- Actualización en `projects`: Theme Styles globales (paleta, fuentes, espaciados base)
- Entradas en `residual_tasks` para cada bloque `unknown` o patrón no mapeable

## Skills que usa

- `bricks-json-schema` — contrato canónico del JSON Bricks (referencia: export real WCM-001)

## Mapping content_block → Bricks element (catálogo MVP)

| content_block.block_type | Bricks element name | Notas |
|---|---|---|
| `hero` | `section` + `container` + `heading` + `text-basic` + `button` + `image` (bg) | Layout flexible |
| `text` | `text` (richtext) | Sanitizado en content-extractor |
| `heading` | `heading` | `level` → `tag` setting |
| `image` | `image` | `asset_id` → media library ID en destino |
| `gallery` | `image-gallery` o `slider` según `layout` | Carousel = Bricks slider |
| `cta` | `button` | `style="primary"` → variable Theme Style `--brand-primary` |
| `form` | `form` | Si Gravity Forms instalado, embed via shortcode element |
| `testimonial` | `block` (container) con custom layout | Template repetible |
| `pricing` | `block` por tier + `loop` si aplica | |
| `faq` | `accordion` | Bricks nativo |
| `product-card` | `woo-product-card` | Solo si WooCommerce activo |
| `video` | `video` | Provider mapping interno |
| `embed` | `code` o `html` | Sanitizado |
| `divider` | `divider` o `spacer` | |
| `nav` | `nav-menu` (header) o custom (footer) | Header siempre como template global |
| `footer` | template global `footer` | |
| `unknown` | NO se mapea → tarea residual + screenshot del bloque origen | |

## Reglas de generación

1. **IDs únicos**: cada elemento Bricks tiene un `id` (6 chars alfanuméricos). Generar deterministas a partir de `(project_id, page_id, order_index, block_type)` para idempotencia.
2. **Jerarquía**: respetar `parent` / `children[]`. Cada página tiene un `section` raíz por bloque top-level.
3. **Settings inline**: solo lo que NO sea variable global. Color de marca → variable. Espaciado de un bloque concreto → inline.
4. **Theme Styles globales**:
   - Paleta: extraída del CSS origen (clusters de colores más usados, top 6).
   - Tipografía: detectar familias body/heading, weights, sizes responsive.
   - Espaciados: rejilla 4px o 8px según patrón detectado.
   - Border-radius global.
5. **Breakpoints**:
   - Detectar media queries del origen.
   - Mapear a breakpoints Bricks (default: mobile <767, tablet 768–991, desktop 992+).
   - Si origen usa breakpoints raros, normalizar y registrar.
6. **Accesibilidad**: cada `image` requiere `alt`. Si origen no lo tenía, usar caption o `headline` del bloque padre como fallback.

## Errores tipados

- `BricksTranspileError` (raíz)
- `UnsupportedBlockError` — block_type no en catálogo (resulta en residual_task, no aborta)
- `SchemaValidationError` — el JSON generado no valida contra el esquema Bricks (BLOQUEANTE)
- `ThemeStyleConflictError` — no se puede resolver una variable global

## Cuándo invocar

- Tras `asset-optimizer` y `seo-preserver` (necesita assets con IDs en destino o R2 y meta SEO).
- Re-transpilación al actualizar el catálogo MVP de bloques.

## Validación obligatoria

- Cada `bricks_json` debe pasar `bricks-json-schema/validate` antes de persistirse.
- Sanity check: ningún elemento huérfano, ningún `parent` apuntando a un id inexistente, ningún `children` con duplicados.

## Notas operativas

- El export real de Bricks (WCM-001) es prerequisito para empezar Fase 2. Sin él, este subagente no se puede implementar.
- Mantener tests con fixtures `tests/fixtures/bricks/<scenario>.json` que cubran cada block_type.
