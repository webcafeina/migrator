# packages/bricks-transpiler

**Núcleo crítico del producto.** Transpilador de `content_blocks` (representación intermedia agnóstica del builder origen) a JSON nativo de **Bricks Builder**.

## Estado

Materializado en **Fase 2** con esquema observacional v1, basado en documentación pública oficial de Bricks Academy + exports de la comunidad. Pendiente de calibración fina cuando llegue el export real (WCM-001).

## API pública

```python
from wcm_bricks_transpiler import (
    TranspileContext,
    transpile_page,
    validate_bricks_page,
    build_theme_styles,
)

ctx = TranspileContext(
    project_id=42,
    page_id=7,
    page_lang="es",
    asset_resolver=lambda asset_id: {
        "url": f"https://example.com/asset-{asset_id}.webp",
        "wp_attachment_id": 1000 + asset_id,
        "width": 1200, "height": 800, "alt_text": "...",
    },
)

result = transpile_page(content_blocks, ctx)
validation = validate_bricks_page(result.content)
assert validation.is_valid

theme = build_theme_styles(project.theme_styles_origin)
```

## Cobertura de bloques (MVP)

| `BlockType` (input) | Bricks element(s) (output) |
|---|---|
| `HERO` | section + container + heading + text + button |
| `HEADING` | heading (envuelto en section+container) |
| `TEXT` | text (envuelto) |
| `IMAGE` | image (envuelto) |
| `GALLERY` | image-gallery (grid) o slider-nested (carousel) |
| `CTA` | button (envuelto) |
| `FORM` | shortcode con Gravity Forms embed |
| `TESTIMONIAL` | block + text (quote) + text-basic (author) |
| `PRICING` | container + N block(s) + heading/text-basic/text/button por tier |
| `FAQ` | accordion con items |
| `PRODUCT_CARD` | woocommerce-product (solo si WP destino tiene WC) |
| `VIDEO` | video (provider=youtube/vimeo); selfhost → residual |
| `EMBED` | code (HTML/JS raw sanitizado) |
| `DIVIDER` | divider o spacer según `style` |
| `NAV` | nav-nested |
| `FOOTER` | section + container + columnas |
| `UNKNOWN` | (sin elementos) → residual obligatorio |

## Reglas de la transpilación

- **IDs deterministas** (`[a-z0-9]{6}`): re-transpilar la misma página produce el mismo JSON → `wp-deployer` puede hacer upsert idempotente.
- **Jerarquía Bricks respetada**: bloques que no emiten su propia section se envuelven automáticamente en una raíz (`section > container > [contenido]`).
- **Theme Styles separados**: el transpilador NO inyecta colores hex inline cuando puede usar variables CSS (`var(--accent)`, `var(--primary)`). La paleta se importa una vez vía Theme Styles globales.
- **Responsive**: settings con sufijo `:tablet_portrait`, `:mobile_landscape`, `:mobile_portrait` (patrón Bricks 2.0+).
- **Validación gate**: `validate_bricks_page` corre antes de persistir; errores `severity="error"` bloquean importación.

## Ejecutar tests

```bash
cd packages/bricks-transpiler
pip install -e ".[dev]" -e ../shared-types
pytest -q
```

## Pendiente

- **WCM-001**: cuando el humano proporcione un export real de Bricks Builder mínimo, comparar con el esquema observacional documentado en `.claude/skills/bricks-json-schema/SKILL.md` y ajustar mappers + tests.
- **Bloques post-MVP**: `query-loop`, `pricing-tables` nativo de Bricks, `template`, `posts`, `breadcrumbs`. Se añadirán según demanda real.

## ADRs relacionados

- ADR-002 — Bricks Builder como page builder destino exclusivo
- ADR-014 — Esquema observacional desde docs públicas (provisional hasta WCM-001)
- ADR-015 — IDs deterministas con blake2b/base36 para idempotencia
