---
name: wix-extraction
description: Patrones específicos para extraer estructura limpia de webs Wix. Documenta CDN parastorage.com, hidratación Velo, selectores característicos de componentes Wix, comportamiento de repeaters y manejo de window.wixBiSession.
---

# Skill — Wix Extraction

## Propósito

Reglas y patrones reutilizables para que `scraper-origin` y `content-extractor` traten correctamente webs construidas con Wix (incluye Editor X, ADI, y Wix Studio).

## Cuándo aplicar

`fingerprinter` ha detectado `builder=wix` con `confidence >= 0.7`.

## Contrato

```python
def extract_wix_page(html: str, url: str, page_dom_tree: dict) -> WixExtractionResult:
    """
    Returns:
        WixExtractionResult(
          page_meta: WixPageMeta,         # title, description, og:*, lang
          sections: list[WixSection],     # cada sección con bloques
          repeaters: list[WixRepeater],   # data binding detectado
          assets_refs: list[AssetRef],    # URLs de imágenes, fonts, videos
          unknown_blocks: list[dict],     # raw HTML fragments para residual_tasks
        )
    """
```

## Señales características de Wix

### CDN
- `static.parastorage.com/services/...`
- `static.wixstatic.com/media/...` (imágenes)
- `static.wixstatic.com/fonts/...`

### JS globales
- `window.wixBiSession`
- `window.viewerModel`
- `window.commonConfig`

### Clases CSS
- Prefijo `comp-` o `wixui-` (p. ej. `wixui-button`, `wixui-rich-text`)
- IDs con formato hexadecimal corto: `id="comp-l1234abc"`

### Estructura DOM
- Raíz: `#site-root` o `#SITE_CONTAINER`
- Header: `#SITE_HEADER`
- Footer: `#SITE_FOOTER`
- Páginas: `#PAGES_CONTAINER` > `#masterPage` y `#PAGES_PAGES` con secciones

## Reglas de extracción

### 1. Esperar hidratación

Antes de capturar HTML, esperar:
```
document.readyState === "complete"
+ esperar 2000 ms extra para Velo (código JS Wix)
+ esperar a que `[data-mesh-id]` con peso significativo (>= 50 elementos) esté presente
```

### 2. Sanitización específica Wix

Eliminar:
- `<script>` con `wix-bi.js`, `viewer-model.js`, hot-update scripts
- Atributos `data-*` de tracking (`data-mesh-id` se preserva, `data-wix-*` se elimina excepto `data-wix-image-link`)
- Inline styles que dependan de variables `--wix-color-N` (resolverlas al valor computado antes)
- Atributos `aria-hidden` que estén en falso (residuo común)

### 3. Detección de componentes característicos

| Wix component | Detección | Bloque normalizado |
|---|---|---|
| Hero / Strip | `[data-mesh-id]` con `section` semántica + bg image grande | `hero` |
| Botón / Link button | `[role=button]` con clase `wixui-button` | `cta` |
| Galería pro | `.wixui-pro-gallery` | `gallery` |
| Slider | `.wixui-slideshow` | `gallery` (layout=carousel) |
| Formulario Wix Forms | `[data-mesh-id*="form"]` | `form` |
| Wix Stores producto | `[data-hook="product-item"]` | `product-card` |
| Repeater | `[data-testid="repeater"]` o `.wixui-repeater` | tratamiento aparte (ver §4) |

### 4. Repeaters (data binding)

Los repeaters Wix son listas con template + dataset. Extraer:
- Template (un solo item, sin datos)
- Dataset: items con campos clave-valor (vía `window.viewerModel` o `window.__INITIAL_STATE__` si disponible)
- Cada item se persiste en `content_blocks` con `block_type` adecuado (testimonial/pricing/product-card) y `content_json.is_repeater_item=true`

### 5. Multilang

Wix usa `?lang=en` o `/en/` indistintamente según configuración. Comprobar:
- `<html lang="...">`
- `<link rel="alternate" hreflang>` (Wix lo declara en `<head>`)
- `window.viewerModel.siteAssets.contextualData.localeData`

### 6. Custom code (Velo)

Si el sitio usa `wix-fetch` o backend Velo, **no migrar lógica de backend**. Marcar como tarea residual: "Lógica Velo a reimplementar en WordPress/PHP".

## Dependencias externas

- Playwright con stealth (ya en `scraper-core`)
- No requiere API key específica de Wix

## Casos límite documentados

- **Wix ADI** (asistente): la estructura puede ser más rígida. Selectores casi idénticos a editor clásico.
- **Wix Studio** (nuevo): clases con prefijo `studio-` añadido. Verificar antes de extraer.
- **Wix Stores con + de 1000 productos**: paginar el scraping; no descargar todas las imágenes en un único batch.
- **Sitios con Members Area / login**: NO migramos el área privada en MVP. Tarea residual.

## Pendiente de calibración

- Validar selectores contra al menos 3 webs Wix reales por nicho (corporativa, e-commerce, blog). Ver WCM-003.
- Documentar variantes encontradas en `tests/fixtures/wix/`.

## Ficheros auxiliares (a crear en Fase 3)

- `patterns.py` — diccionario de regex/selectores
- `tests/fixtures/wix/corporate-1.html` — sitio de ejemplo
- `tests/fixtures/wix/expected-corporate-1.json` — salida esperada
