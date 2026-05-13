---
name: bricks-json-schema
description: Esquema canónico del JSON de Bricks Builder con ejemplos por tipo de elemento. Define el contrato que produce bricks-transpiler y consume wp-deployer. Incluye reglas de IDs únicos, parent/children, settings inline vs Theme Styles globales.
---

# Skill — Bricks JSON Schema

> Estado: **esquema observacional v1**, derivado de documentación pública oficial de Bricks Academy + exports de la comunidad (wpgaurav/bricks-skills, sabiertas/bricks-mcp-server). Pendiente de calibración fina cuando llegue el export real (WCM-001).

## Propósito

Definir el contrato del JSON que importa Bricks Builder, para que `bricks-transpiler` produzca output válido y `wp-deployer` lo consuma sin sorpresas.

## Estructura top-level de una página

Bricks almacena el contenido de una página en el post meta `_bricks_page_content_2` como un array de elementos:

```json
[
  {
    "id": "sec001",
    "name": "section",
    "parent": "0",
    "children": ["con001"],
    "settings": { ... },
    "label": "Hero Section"
  },
  {
    "id": "con001",
    "name": "container",
    "parent": "sec001",
    "children": ["hed001", "txt001", "btn001"],
    "settings": { ... }
  },
  ...
]
```

Encabezado (`_bricks_page_header`) y pie (`_bricks_page_footer`) son templates separados con la misma estructura. Theme Styles vivien en un option global (`bricks_global_settings`), exportable aparte.

## Reglas críticas

### IDs

- **Formato**: 6 chars alfanuméricos minúsculos `[a-z0-9]{6}`.
- **Prefijo DOM**: cuando se renderizan, las clases CSS llevan `brxe-<id>` (p. ej. `brxe-abc123`). En el JSON solo el ID puro.
- **Únicos por página**. Se recomienda generación determinista a partir de `(project_id, page_id, order_index, block_type, sub_index)` hasheado + truncado.
- **`parent`**: string con el ID del padre, o `"0"` si es top-level. Nota: es string `"0"`, no integer.
- **`children[]`**: array de strings IDs en orden de aparición.

### Jerarquía válida

| Element | Puede contener | Vive dentro de |
|---|---|---|
| `section` | `container`, `block`, otros | solo top-level (parent `"0"`) |
| `container` | cualquier elemento layout o atómico | `section`, otro `container`, `block` |
| `block` | igual que container, más restringido | igual que container |
| atómicos (heading/text/image/button/icon) | nada | dentro de container/block |
| `accordion` | items propios | dentro de container/block |
| `slider-nested` | slides (cada slide es un container) | dentro de container/block |
| `nav-menu`, `nav-nested` | configuración propia | en header template |

## Catálogo MVP de element names

Confirmados desde docs Bricks + exports comunidad:

### Layout
- `section` — wrapper top-level full-width
- `container` — max-width wrapper, layout flex
- `block` — div flex genérico
- `div` — div simple sin layout específico

### Texto
- `heading` — h1–h6 (`tag` setting)
- `text` — richtext (párrafos con HTML)
- `text-basic` — texto plano, 1 línea, sin richtext

### Media
- `image` — img con responsive sizes
- `image-gallery` — galería grid/masonry/carousel
- `video` — provider YouTube/Vimeo/self-host
- `icon` — librerías Themify/FontAwesome/Ionicons
- `icon-box` — icono + texto en contenedor

### Interactivos
- `button` — CTA con link
- `accordion` — items expandibles (para FAQ)
- `slider-nested` — carrusel; cada slide es contenedor anidado
- `nav-menu` — menu WP nativo
- `nav-nested` — menu Bricks 2.0+ (preferente)
- `form` — formulario nativo Bricks
- `shortcode` — embed de Gravity Forms / WooCommerce / cualquier shortcode

### Utilidad
- `divider` — línea separadora
- `spacer` — espacio vacío
- `code` — HTML/JS raw (sanitizado)

### WooCommerce
- `woocommerce-products` — query de productos
- `woocommerce-product` — tarjeta de producto individual

### En post-MVP (no se implementan en Fase 2)
- `nav-pro`, `template`, `query-loop`, `pricing-tables`, `posts`, `breadcrumbs`, `pagination`

## Settings

Las keys de `settings` usan dos convenciones:

### Settings globales con prefijo `_` (afectan al render del elemento)

| Key | Valor | Notas |
|---|---|---|
| `_typography` | `{font-family, font-size, font-weight, line-height, color: {raw: "..."}, text-align}` | Sirve para cualquier elemento con texto |
| `_padding` | `{top, right, bottom, left}` (strings con unidad) | |
| `_margin` | `{top, right, bottom, left}` | |
| `_background` | `{color: {raw: "..."}, image: {url, id, repeat, position, size}}` | |
| `_border` | `{width: {t,r,b,l}, style, color: {raw}, radius: {t,r,b,l}}` | |
| `_cssGlobalClasses` | `["class-id-1", "class-id-2"]` | IDs de global classes |
| `_cssCustom` | `string` | CSS arbitrario inline |
| `_cssId` | `string` | ID CSS custom (sobreescribe `brxe-*`) |
| `_visibility` | `{mobile: bool, tablet: bool, desktop: bool}` | hide por breakpoint |

### Settings específicos por element name

Sin prefijo. Ejemplos:

| Element | Settings específicos |
|---|---|
| `heading` | `tag` ("h1".."h6"), `text` (string HTML safe) |
| `text` | `text` (richtext HTML) |
| `text-basic` | `text` (plain) |
| `image` | `image: {id, url, alt, width, height, size}` |
| `button` | `text`, `link: {type, url, target, rel}`, `style` ("primary"|"secondary"), `icon: {library, icon}`, `iconPosition` |
| `icon` | `icon: {library, icon}`, `size` |
| `accordion` | `items: [{title, content, open}]`, `style` |
| `slider-nested` | (los slides como children container) + `options: {autoplay, loop, navigation, pagination}` |
| `image-gallery` | `images: [{id, url, ...}]`, `layout`, `columns`, `lightbox` |
| `nav-menu` | `menu` (WP menu ID), `layout`, `mobile-breakpoint` |
| `form` | `fields: [...]`, `submitAction`, `emailConfig` |
| `shortcode` | `shortcode` (string raw) |
| `video` | `provider`, `videoId` (o `url`), `autoplay`, `controls` |
| `code` | `code` (string), `executeCode` (bool) |
| `divider` | `style`, `color: {raw}`, `width`, `height` |
| `spacer` | `height` (string con unidad o responsive) |

### Valores responsive

Algunas keys aceptan valores responsive por breakpoint. Hay dos patrones observados:

**Patrón A** — sufijo `:tablet_portrait`, `:mobile_landscape`, `:mobile_portrait`:
```json
{
  "_padding": {"top": "80px"},
  "_padding:tablet_portrait": {"top": "60px"},
  "_padding:mobile_portrait": {"top": "40px"}
}
```

**Patrón B** — objeto anidado por breakpoint (legado en algunas keys):
```json
{
  "_padding": {
    "desktop": {"top": "80px"},
    "tablet":  {"top": "60px"},
    "mobile":  {"top": "40px"}
  }
}
```

Usamos **patrón A** (sufijo) por defecto: es el que aparece en exports recientes y en docs Bricks 2.0+.

### Breakpoints estándar Bricks

| Nombre | Width |
|---|---|
| `desktop` | ≥ 992px (default) |
| `tablet_portrait` | ≤ 991px |
| `mobile_landscape` | ≤ 767px |
| `mobile_portrait` | ≤ 478px |

## Variables CSS de Theme Styles

Bricks 2.0+ expone variables CSS estandarizadas en `<html>` cuando Theme Styles está activo (Core Framework / Automatic CSS reusan estos nombres):

- **Espaciado**: `--spacing-4xs` ... `--spacing-4xl` (fluid clamp)
- **Tipografía**: `--text-xs` ... `--text-4xl`
- **Colores**: `--primary`, `--secondary`, `--tertiary`, con variantes `-5`, `-10`, `-20` ... `-90` (opacidad/luminosidad)
- **Radio**: `--radius-xs` ... `--radius-full`
- **Sombras**: `--shadow-xs` ... `--shadow-xl`

El transpilador genera Theme Styles que **respeta esta nomenclatura** para máxima portabilidad.

## Theme Styles global (`bricks_global_settings`)

Estructura observada:

```json
{
  "theme_styles": [
    {
      "id": "webcafeina-default",
      "label": "Webcafeína Default",
      "settings": {
        "section": {
          "_padding": {"top": "80px", "bottom": "80px"}
        },
        "heading": {
          "_typography": {"font-family": "Inter", "font-weight": "700"}
        },
        "button": {
          "_background": {"color": {"raw": "var(--primary)"}},
          "_padding": {"top": "12px", "right": "24px", "bottom": "12px", "left": "24px"}
        }
      },
      "conditions": []
    }
  ],
  "colorPalette": [
    {"name": "primary", "color": "#171009"},
    {"name": "secondary", "color": "#2B1A0E"},
    {"name": "text", "color": "#F2E8D2"},
    {"name": "accent", "color": "#B1F100"},
    {"name": "detail-brown", "color": "#5A3519"}
  ],
  "breakpoints": {
    "desktop": 992,
    "tablet_portrait": 991,
    "mobile_landscape": 767,
    "mobile_portrait": 478
  }
}
```

## Importación al destino

No hay endpoint REST oficial de Bricks para import directo. Estrategias soportadas:

1. **Vía WP-CLI** (preferente, ver skill `wpcli-ssh`):
   ```
   wp post update <post_id> --post_meta='_bricks_page_content_2=<content_json>'
   wp option update bricks_global_settings <settings_json> --format=json
   ```
2. **Vía meta_input en POST `/wp-json/wp/v2/pages`** (skill `wp-rest-bulk`):
   ```json
   {
     "title": "...",
     "slug": "...",
     "status": "publish",
     "template": "bricks-template",
     "meta": {"_bricks_page_content_2": "<content_json_string>"}
   }
   ```
3. **Templates JSON import** (manual, para Theme Styles iniciales): vía wp-admin → Bricks → Templates → Import.

## Validación

`packages/bricks-transpiler/src/wcm_bricks_transpiler/validator.py` (Fase 2):

```python
def validate_bricks_page(content: list[dict]) -> ValidationResult:
    # 1. Cada elemento tiene id, name, parent, children, settings
    # 2. ids únicos en la página
    # 3. parent apunta a id existente o "0"
    # 4. children consistente con parents (relación bidireccional intacta)
    # 5. name dentro del catálogo soportado
    # 6. settings tienen las keys obligatorias según element name
    # 7. tipos: parent es string, children es list[str], settings es dict
    ...
```

## Pendiente de calibración (WCM-001)

Cuando el humano proporcione un export real de Bricks Builder mínimo:

1. Guardar en `.claude/skills/bricks-json-schema/reference-export.json`.
2. Comparar con el esquema observacional documentado aquí.
3. Ajustar `packages/bricks-transpiler/` para coincidir exactamente.
4. Re-ejecutar tests con fixtures actualizadas.

Hasta entonces, el transpilador produce JSON que **debería** ser válido para Bricks 1.9+ / 2.0+ basándose en docs públicas. Riesgos conocidos:

- Patrón responsive (A vs B): asumido patrón A.
- Estructura exacta de Theme Styles: aproximada.
- Keys específicas por element no exhaustivamente documentadas en docs públicas.

## Ficheros que vivirán en esta carpeta

```
.claude/skills/bricks-json-schema/
├── SKILL.md                    # este fichero
├── schema.json                 # JSON Schema (Draft 2020-12)
├── examples/
│   ├── minimal-page.json       # 1 section + 1 container + 1 heading
│   ├── hero-with-cta.json      # patrón hero típico
│   └── theme-styles.json       # Theme Styles ejemplo paleta Webcafeína
└── reference-export.json       # PENDIENTE (WCM-001)
```

## Fuentes consultadas (documentación pública)

- Bricks Academy oficial — Template Library, Theme Styles, Style Manager, Global Elements
- Bricks Community Forum — element ID format `[a-z0-9]{6}`
- wpgaurav/bricks-skills — ejemplos JSON de bloques completos
- sabiertas/bricks-mcp-server — categorías de elements (24 totales) + workflow add/duplicate
- BricksSync docs — workflow export/import
- Core Framework / Automatic CSS docs — variables CSS estandarizadas
