---
name: bricks-json-schema
description: Esquema canónico del JSON de Bricks Builder con ejemplos por tipo de elemento. Define el contrato que produce bricks-transpiler y consume wp-deployer. Incluye reglas de IDs únicos, parent/children, settings inline vs Theme Styles globales.
---

# Skill — Bricks JSON Schema

> ⚠️ Este skill está en estado **provisional** hasta resolver WCM-001 (export real de Bricks Builder mínimo). El esquema documentado aquí se basa en observación de exports públicos y deberá validarse contra un export real antes de la Fase 2.

## Propósito

Definir el contrato del JSON que importa Bricks Builder, para que `bricks-transpiler` produzca output válido y `wp-deployer` lo consuma sin sorpresas.

## Estructura general

Una página Bricks exportada es un JSON con esta forma:

```json
{
  "content": [
    {
      "id": "abc123",
      "name": "section",
      "parent": 0,
      "children": ["def456", "ghi789"],
      "settings": { ... },
      "label": "Hero Section"
    },
    ...
  ],
  "header": [ ... ],
  "footer": [ ... ],
  "theme_styles": { ... },
  "version": "1.x"
}
```

## Reglas críticas

### IDs

- `id`: string de 6 chars alfanuméricos `[a-z0-9]{6}`
- Único por página. Se recomienda generación determinista por `(project_id, page_id, order_index, block_type)` hasheado y truncado.
- `parent`: el `id` del padre, o `0` si es top-level.
- `children[]`: array de `id`s en orden de aparición.

### Jerarquía válida

- `section` solo top-level (parent=0).
- `container` puede vivir dentro de `section` o de otro `container`.
- `block` similar a container, pero más restringido para layouts.
- Elementos atómicos (`heading`, `text`, `image`, `button`, `icon`) vivien dentro de containers/blocks, no como hijos directos de `section` (excepción en patrones legacy: aceptable pero subóptimo).

## Catálogo de elementos (MVP)

| Element `name` | Settings clave | Notas |
|---|---|---|
| `section` | `tag`, `min-height`, `bg-image`, `bg-color`, `padding`, `max-width-content` | Wrapper top-level |
| `container` | `flex-direction`, `gap`, `justify-content`, `align-items`, `padding`, `bg-color` | Layout flex |
| `block` | similar a container | Más simple |
| `heading` | `tag` (h1-h6), `text`, `typography`, `color`, `align` | |
| `text-basic` | `text`, `typography`, `color` | Para 1 línea |
| `text` | `text` (richtext HTML), `typography`, `color` | Para párrafos |
| `image` | `image.id` (attachment WP), `image.url`, `image.alt`, `width`, `height`, `object-fit` | |
| `button` | `text`, `link.type`, `link.url`, `style`, `typography`, `bg-color`, `padding` | |
| `icon` | `icon.library`, `icon.name`, `size`, `color` | FontAwesome / themify / Ionicons |
| `accordion` | `items[]` (each: `title`, `content`, `open`), `style` | Para FAQ |
| `slider-nested` | `slides[]` (each: array de nested elements), `options` | Carrusel |
| `image-gallery` | `images[]`, `layout` (grid/masonry), `columns`, `lightbox` | |
| `nav-menu` | `menu` (WP menu id), `style`, `mobile-breakpoint` | |
| `form` | `fields[]`, `submit-action`, `email-config` | Forms Bricks nativo (en MVP usaremos Gravity Forms embed via shortcode) |
| `shortcode` | `shortcode` (string) | Para embed Gravity Forms, WooCommerce, etc. |
| `video` | `provider`, `url-or-id`, `autoplay`, `controls` | |
| `code` | `code` (raw HTML/JS) | Solo para embeds sanitizados |
| `divider` | `style`, `color`, `width` | |
| `spacer` | `height` | |
| `woo-products` | `query`, `columns`, `style` | Solo si WooCommerce activo |
| `woo-product` | `product-id`, `display-elements[]` | Tarjeta de producto |

## Theme Styles globales

```json
{
  "theme_styles": {
    "colors": {
      "primary": "#171009",
      "secondary": "#2B1A0E",
      "accent": "#B1F100",
      "text": "#F2E8D2",
      "...": "..."
    },
    "typography": {
      "body": {"font-family": "Inter, sans-serif", "size": "16px", "line-height": "1.6"},
      "h1": {"font-family": "...", "size": "clamp(2rem, 5vw, 3.5rem)", "weight": "700"},
      "...": "..."
    },
    "breakpoints": {
      "mobile": 767,
      "tablet": 991,
      "desktop": 1200
    },
    "spacing": {
      "section-padding-y": "80px",
      "container-padding-x": "24px",
      "...": "..."
    }
  }
}
```

## Settings responsive

Bricks soporta valores por breakpoint:

```json
{
  "padding": {
    "desktop": {"top": "80px", "bottom": "80px"},
    "tablet":  {"top": "60px", "bottom": "60px"},
    "mobile":  {"top": "40px", "bottom": "40px"}
  }
}
```

## Validación

`bricks-json-schema/validate.py` (a implementar en Fase 2):

```python
def validate_bricks_page(payload: dict) -> ValidationResult:
    # 1. Top-level keys obligatorios
    # 2. Cada elemento tiene id, name, parent, children, settings
    # 3. ids únicos en la página
    # 4. parent apunta a id existente o 0
    # 5. children list consistente con parents
    # 6. name dentro del catálogo soportado
    # 7. settings tienen las keys obligatorias según element name
    ...
```

## Importación

Vía WP-CLI (preferente para bulk):
```
wp bricks import-content --file=page-1.json --post-id=42
```

Vía REST API (singular):
```
POST /wp-json/bricks/v1/import
```

## Pendiente de calibración

- **WCM-001**: obtener export real de una página Bricks Builder mínima (header + hero + texto + CTA + section + container) y guardarlo en `reference-export.json` aquí mismo. Ajustar el esquema documentado al real.
- Identificar el endpoint REST correcto y los permisos requeridos (Application Password con `manage_options`).
- Verificar cómo Bricks gestiona los attachment IDs cuando la imagen ya está en la media library con un slug coincidente.

## Ficheros que vivirán en esta carpeta

```
.claude/skills/bricks-json-schema/
├── SKILL.md                    # este fichero
├── reference-export.json       # WCM-001
├── schema.json                 # JSON Schema (Draft 2020-12) generado a partir de la referencia
├── validate.py                 # validador (Fase 2)
└── examples/
    ├── minimal-page.json
    ├── hero-with-cta.json
    └── full-corporate-home.json
```
