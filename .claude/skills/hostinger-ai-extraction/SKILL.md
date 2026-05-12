---
name: hostinger-ai-extraction
description: Patrones para extraer estructura limpia de webs construidas con Hostinger AI Builder. Las webs AI de Hostinger tienen estructura predecible con bloques etiquetados; documenta selectores característicos, comportamiento de hidratación y manejo de plantillas.
---

# Skill — Hostinger AI Extraction

## Propósito

Reglas para `scraper-origin` y `content-extractor` cuando el origen es Hostinger AI Builder (también conocido como Zyro AI Builder, su predecesor, comparte muchos patrones).

## Cuándo aplicar

`fingerprinter` ha detectado `builder=hostinger_ai` con `confidence >= 0.7`.

## Contrato

```python
def extract_hostinger_page(html: str, url: str, page_dom_tree: dict) -> HostingerExtractionResult:
    """
    Returns:
        HostingerExtractionResult(
          page_meta: PageMeta,
          sections: list[Section],
          assets_refs: list[AssetRef],
          unknown_blocks: list[dict],
        )
    """
```

## Señales características

### CDN y dominios
- Imágenes: `assets.hostinger.com/...` o `cdn.hostinger.com/...`
- Hosting visible: `Server: hostinger` (header)

### Hidratación
- Esperar `[data-hostai-loaded="true"]` (atributo que el builder coloca cuando termina)
- Fallback: `document.readyState === "complete"` + 1.5 s

### Clases y atributos
- `data-section-id="..."` en cada sección (estable)
- `data-block-type="hero" | "text" | "image" | "gallery" | "cta" | "form" | "testimonial" | "faq" | "pricing"` ← **mapeo directo a nuestro catálogo de block_types**
- `data-theme-color` con paleta del sitio (extraer para Theme Styles)

## Reglas de extracción

### 1. Estructura predecible

Cada sección Hostinger AI tiene la forma:

```html
<section data-section-id="s_xxxx" data-block-type="hero" class="hostai-section">
  <div class="hostai-container">
    <h1 data-role="headline">...</h1>
    <p data-role="subheadline">...</p>
    <a data-role="cta" href="...">...</a>
    <img data-role="bg-image" src="...">
  </div>
</section>
```

Esto es ORO: el mapping a `content_blocks` es casi 1:1.

### 2. Sanitización

Eliminar:
- `<script>` con `hostai-runtime.js`, `analytics.js`
- Inline styles `--hostai-color-*` (resolver a hex)
- `data-hostai-internal-*` (debugging del builder)

### 3. Theme detection

Variables CSS expuestas en `<html>`:
- `--hostai-primary`, `--hostai-secondary`, `--hostai-accent` → paleta
- `--hostai-font-heading`, `--hostai-font-body` → tipografía
- `--hostai-radius-base` → border radius

Persistir en `project.theme_styles_origin`.

### 4. AI-generated content marker

Algunas páginas tienen `data-hostai-generated="true"` indicando contenido generado por la IA del builder. Tratarlo igual que cualquier contenido, pero anotarlo en `audit_log` por si el cliente quiere revisar.

### 5. Formularios

Los forms Hostinger usan `<form data-hostai-form>` con endpoint propio. **No funcionará en destino** (el endpoint apunta a infraestructura Hostinger). El form debe recrearse con Gravity Forms. La preservación se limita a:
- Campos
- Validaciones
- Mensaje de éxito

## Dependencias externas

- Playwright con stealth
- No requiere credenciales Hostinger

## Casos límite documentados

- **Webs migradas desde Zyro**: pueden tener `data-zyro-*` en lugar de `data-hostai-*`. Aplicar fallback con mismo significado.
- **Webs con custom code**: el builder permite inyectar HTML/CSS custom. Capturar como `embed` y revisar manualmente.
- **Sitios con login propio del builder**: no se migra el área privada.

## Pendiente de calibración

- Validar contra al menos 3 webs Hostinger AI reales. Ver WCM-003.

## Ficheros auxiliares (a crear en Fase 3)

- `patterns.py`
- `tests/fixtures/hostinger/*.html`
