---
name: webflow-extraction
description: Patrones para extraer estructura de webs Webflow. Documenta uso de data-w-id, sistema de classes Webflow, animaciones IX2, CMS Collections, y por qué se usa sidecar Puppeteer en lugar de Playwright para esta plataforma.
---

# Skill — Webflow Extraction

## Propósito

Reglas para `scraper-origin` y `content-extractor` cuando el origen es Webflow. Webflow es notablemente más complejo de scrapear que Wix/Hostinger debido a sus animaciones IX2 y al sistema de classes anidado.

## Cuándo aplicar

`fingerprinter` ha detectado `builder=webflow` con `confidence >= 0.7`.

## ¿Por qué sidecar Puppeteer?

En benchmarks internos, Playwright tiene problemas para esperar correctamente la inicialización de **Webflow IX2** (Interactions 2.0). Puppeteer con `waitForFunction(() => window.Webflow && window.Webflow.ready)` resulta más fiable. Por eso `scraper-origin` arranca un proceso Node sidecar solo para builder=webflow.

## Contrato

```python
def extract_webflow_page(html: str, url: str, page_dom_tree: dict) -> WebflowExtractionResult:
    """
    Returns:
        WebflowExtractionResult(
          page_meta: PageMeta,
          sections: list[Section],
          cms_items: list[CmsItem],         # Webflow CMS Collections
          ix2_interactions: list[Ix2Spec],  # animaciones declaradas
          assets_refs: list[AssetRef],
          unknown_blocks: list[dict],
        )
    """
```

## Señales características

### CDN
- `assets.website-files.com/...` (assets de Webflow)
- `cdn.prod.website-files.com/...`
- `uploads-ssl.webflow.com/...` (legado)

### JS globales
- `window.Webflow` (objeto con métodos `.ready()`, `.destroy()`, `.require()`)
- `Webflow.ready(fn)`

### Atributos
- `data-w-id="abc123def456"` (id único por elemento, **clave para mapear IX2**)
- `data-wf-page` (en `<html>`, id de la página actual)
- `data-wf-site` (en `<html>`, id del proyecto Webflow)
- `data-collection-list-id` (CMS Collection list)

### Clases
- `.w-button`, `.w-nav`, `.w-container`, `.w-row`, `.w-col-*`
- `.w-form`, `.w-input`, `.w-radio`, `.w-checkbox`
- `.w-tab-link`, `.w-tab-pane`
- `.w-dropdown`, `.w-slider`, `.w-lightbox`
- Clases custom del proyecto: nombres en kebab-case según el diseñador

## Reglas de extracción

### 1. Esperar inicialización completa

```javascript
await page.waitForFunction(() => {
  return window.Webflow && Array.isArray(window.Webflow._ready) === false;
});
await page.waitForTimeout(1500);  // settle IX2
```

### 2. Snapshot del IX2

`window.Webflow.ix2.store.getState().ixData` contiene la definición de todas las animaciones. Persistirlo para análisis.

**IMPORTANTE**: en MVP **NO migramos IX2 a Bricks**. Las animaciones se pierden. Generar tarea residual por cada interacción significativa: "Recrear animación X de Webflow en Bricks con CSS/JS custom".

### 3. CMS Collections

Si la página usa CMS:
- Detectar `[data-collection-list-id]`
- Para cada item del CMS: extraer campos clave-valor del DOM
- Persistir como bloques `content_block.type` apropiado, con `content_json.collection_id` para reagrupar en destino

> En MVP, los CMS items se migran como posts/páginas estándar de WordPress. CPT (Custom Post Types) si el cliente lo solicita explícitamente (no por defecto).

### 4. Sanitización Webflow

Eliminar:
- `<script>` con `webflow.js`, `jquery-*.min.js` (ya no necesarios en Bricks)
- Atributos `data-w-*` excepto `data-w-id` (necesario para correlación de IX2)
- Clases `.w-*` que no aporten layout (las que aportan: convertirlas a equivalente Bricks/Tailwind antes de descartar)

### 5. Formularios

`<form>` con `.w-form` envía a Webflow Forms (endpoint propio). No funciona en destino. Recrear con Gravity Forms (mismos campos + validaciones).

### 6. Theme

Webflow no expone variables CSS directamente. La paleta se infiere:
- Recolectar todos los `color`, `background-color` computados en h1, h2, body, .button principales
- Cluster top-6 (k-means simple sobre HSL)
- Persistir como `project.theme_styles_origin`

## Casos límite documentados

- **Webflow Ecommerce**: productos vienen como CMS Collection especial. Mapear a WooCommerce.
- **Webflow Logic** (workflows visuales): no migrables. Tarea residual.
- **Memberships**: no migrables en MVP.
- **Sitios con custom code en `<head>`**: preservar tal cual en `wp-config` o en el header del tema Bricks (post revisión humana).

## Pendiente de calibración

- Validar con 3 webs Webflow reales (corporate, portfolio, e-commerce). Ver WCM-003.

## Dependencias externas

- Node 20+ (sidecar Puppeteer)
- `puppeteer` y `puppeteer-extra-plugin-stealth`

## Ficheros auxiliares (a crear en Fase 3)

- `puppeteer-sidecar.js`
- `patterns.py`
- `tests/fixtures/webflow/*.html`
