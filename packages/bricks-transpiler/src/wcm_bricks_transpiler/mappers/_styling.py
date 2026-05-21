"""Conversión computed styles del origen → Bricks settings (v0.23.0).

Helper compartido por todos los mappers atómicos. Convierte un dict
`{color, font-size, padding, ...}` (obtenido por `getComputedStyle()` en
el origen) en el shape exacto que espera Bricks Builder:

- `color` SIEMPRE envuelto como `{"raw": "..."}` — un string pelado lo
  descarta Bricks silenciosamente (confirmado en `bricks-skills/bricks-layouts.md`).
- `_typography`, `_padding`, `_background`, `_border`, `_layout` con
  keys exactas que documenta el repo `wpgaurav/bricks-skills`.
- Responsive con sufijo `:tablet_portrait` en la misma key (NO objeto
  anidado).

Patrón arquitectónico:
- Cuando el bundle de settings de un elemento es rico (tipografía
  completa, padding distinto del default, etc.) se registra como una
  **globalClass** `wcm-<digest>` en `ctx.global_classes` y se referencia
  desde el elemento via `_cssGlobalClasses`. Esto:
    1. Reduce el postmeta (1 definición vs N elementos)
    2. Hace la clase editable desde el panel Bricks (cambias UNA y se
       propaga a todos los elementos que la usan).
    3. Permite dedup automática por hash de settings.

- Cuando el styling es trivial (solo 1-2 propiedades) se emite inline
  sin globalClass (no merece la indirección).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from wcm_bricks_transpiler.mappers._types import MapperContext

#: Mínimo de propiedades CSS interesantes que justifica registrar una
#: globalClass (vs emitir inline). Si tras filtrar el styling tiene
#: <THRESHOLD properties, el helper emite inline para no inflar
#: `global_classes` con clases triviales.
GLOBAL_CLASS_MIN_PROPS = 3


def _slug(value: str) -> str:
    """`Albra Sans Light` → `albra-sans-light`. Útil para nombres de
    globalClasses derivados del computed value.
    """
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def _color_to_bricks(value: str | None, theme_palette: dict[str, str] | None = None) -> dict | None:
    """Convierte `rgb(...)` / `#xxx` / `var(--...)` a `{"raw": value}`.

    Si la `theme_palette` matchea exactamente (LAB delta ≤5 idealmente,
    en MVP solo equality lowercased), sustituye por `var(--bricks-color-X)`.

    Retorna None si `value` es vacío/inválido para que el mapper omita
    la key (Bricks prefiere ausencia a `{"raw": ""}`).
    """
    if not value or value.strip().lower() in ("none", "transparent", "rgba(0, 0, 0, 0)", "initial", "inherit"):
        return None
    v = value.strip()
    # Substitución a variable de palette si matchea.
    if theme_palette:
        for slot, hex_or_rgb in theme_palette.items():
            if hex_or_rgb and v.lower() == hex_or_rgb.lower():
                return {"raw": f"var(--bricks-color-{slot})"}
    return {"raw": v}


def _parse_shorthand_four_sides(value: str) -> dict[str, str] | None:
    """`padding: "16px 32px 8px 24px"` → `{top, right, bottom, left}`.

    Soporta 1, 2, 3, 4 valores siguiendo la regla CSS shorthand:
    - 1 → todos
    - 2 → vertical, horizontal
    - 3 → top, horizontal, bottom
    - 4 → top, right, bottom, left
    """
    if not value or value.strip() in ("0px", "0", "auto"):
        return None
    parts = value.strip().split()
    if not parts or parts[0] in ("none", "initial", "inherit"):
        return None
    if len(parts) == 1:
        v = parts[0]
        return {"top": v, "right": v, "bottom": v, "left": v}
    if len(parts) == 2:
        v_y, v_x = parts
        return {"top": v_y, "right": v_x, "bottom": v_y, "left": v_x}
    if len(parts) == 3:
        v_t, v_x, v_b = parts
        return {"top": v_t, "right": v_x, "bottom": v_b, "left": v_x}
    # 4+
    v_t, v_r, v_b, v_l = parts[:4]
    return {"top": v_t, "right": v_r, "bottom": v_b, "left": v_l}


def _font_family_clean(value: str) -> str | None:
    """`"Albra Sans", "Helvetica", sans-serif` → `Albra Sans` (el primero
    no genérico). Devuelve None si solo hay families internas Wix
    (`wfont_*`, `wf_*`) o solo sans-serif/serif/system-ui."""
    if not value:
        return None
    families = [f.strip().strip('"\'') for f in value.split(",")]
    generics = {"sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui", "-apple-system"}
    for fam in families:
        low = fam.lower().replace(" ", "")
        if low.startswith(("wfont_", "wf_")):
            continue
        if low in generics:
            continue
        if fam:
            return fam
    return None


def _styles_to_bricks_settings(
    element_styles: dict[str, str] | None,
    ctx: MapperContext,
) -> dict[str, Any]:
    """Mapea computed styles → Bricks settings (`_typography`, `_padding`,
    `_background`, `_border`, `_layout`).

    El caller decide si pone el resultado **inline** o lo registra como
    globalClass via `_get_or_create_global_class`. Este helper NO toca
    `ctx.global_classes` (solo lee `theme_styles` para color matching).
    """
    if not element_styles:
        return {}

    out: dict[str, Any] = {}
    palette = None
    if ctx.theme_styles and isinstance(ctx.theme_styles, dict):
        palette = ctx.theme_styles.get("colors")

    # ---- typography ----
    typography: dict[str, Any] = {}
    if (v := _color_to_bricks(element_styles.get("color"), palette)) is not None:
        typography["color"] = v
    if (v := element_styles.get("font-family")):
        clean = _font_family_clean(v)
        if clean:
            typography["font-family"] = clean
    if (v := element_styles.get("font-size")):
        typography["font-size"] = v
    if (v := element_styles.get("font-weight")):
        if v.strip() not in ("normal", "400"):
            typography["font-weight"] = v.strip()
    if (v := element_styles.get("font-style")):
        if v.strip() not in ("normal",):
            typography["font-style"] = v.strip()
    if (v := element_styles.get("line-height")):
        if v.strip() not in ("normal",):
            typography["line-height"] = v.strip()
    if (v := element_styles.get("letter-spacing")):
        if v.strip() not in ("normal", "0px"):
            typography["letter-spacing"] = v.strip()
    if (v := element_styles.get("text-align")):
        if v.strip() not in ("start", "left"):
            typography["text-align"] = v.strip()
    if (v := element_styles.get("text-transform")):
        if v.strip() not in ("none",):
            typography["text-transform"] = v.strip()
    if (v := element_styles.get("text-decoration")):
        if v and "none" not in v.lower():
            typography["text-decoration"] = v.strip()
    if typography:
        out["_typography"] = typography

    # ---- background ----
    background: dict[str, Any] = {}
    if (v := _color_to_bricks(element_styles.get("background-color"), palette)) is not None:
        background["color"] = v
    if (v := element_styles.get("background-image")):
        # Si es url(...) Bricks lo acepta como image.url. Si es gradient,
        # mete el gradient string entero como `_gradient` (Bricks lo
        # acepta como CSS literal).
        v = v.strip()
        if v.startswith("url("):
            # Extraer URL del url("...")
            inner = re.search(r'url\(["\']?([^"\')]+)["\']?\)', v)
            if inner:
                background["image"] = {"url": inner.group(1)}
        elif "gradient" in v.lower():
            background["_gradient"] = v
    if background:
        out["_background"] = background

    # ---- padding / margin / gap ----
    if (v := element_styles.get("padding")):
        parsed = _parse_shorthand_four_sides(v)
        if parsed:
            out["_padding"] = parsed
    if (v := element_styles.get("margin")):
        parsed = _parse_shorthand_four_sides(v)
        if parsed:
            out["_margin"] = parsed
    if (v := element_styles.get("gap")):
        if v.strip() not in ("0px", "normal", "0"):
            out["_gap"] = v.strip()

    # ---- border + radius ----
    if (v := element_styles.get("border-radius")):
        parsed = _parse_shorthand_four_sides(v)
        if parsed:
            out["_border"] = {"radius": parsed}
    if (v := element_styles.get("box-shadow")):
        if v.strip() not in ("none",):
            out.setdefault("_border", {})["_boxShadow"] = v.strip()

    # ---- layout (display/flex/grid) ----
    layout: dict[str, Any] = {}
    if (v := element_styles.get("display")) and v.strip() in ("flex", "grid", "inline-flex"):
        layout["display"] = v.strip()
        if v.strip() in ("flex", "inline-flex"):
            if (fd := element_styles.get("flex-direction")):
                layout["direction"] = fd.strip()
            if (jc := element_styles.get("justify-content")):
                layout["justify-content"] = jc.strip()
            if (ai := element_styles.get("align-items")):
                layout["align-items"] = ai.strip()
    if layout:
        out["_layout"] = layout

    return out


def _settings_digest(settings: dict[str, Any]) -> str:
    """6-char hex digest determinista de un settings dict.

    Usado por `_get_or_create_global_class` para dedup. JSON sort_keys
    para que el orden de inserción no afecte.
    """
    import json
    payload = json.dumps(settings, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:6]


def _get_or_create_global_class(
    settings: dict[str, Any],
    prefix: str,
    ctx: MapperContext,
) -> str:
    """Registra `settings` como globalClass en `ctx.global_classes` con
    dedup por digest. Devuelve el `name` para referenciar en
    `_cssGlobalClasses`.

    `prefix` se incorpora al name para facilitar lectura humana
    (`wcm-h1-abc123`, `wcm-cta-def456`).
    """
    digest = _settings_digest(settings)
    name = f"wcm-{prefix}-{digest}"
    for entry in ctx.global_classes:
        if entry.get("id") == name:
            return name
    ctx.global_classes.append({
        "id": name,
        "name": name,
        "settings": settings,
    })
    return name


def styles_inline_or_class(
    element_styles: dict[str, str] | None,
    *,
    prefix: str,
    ctx: MapperContext,
) -> tuple[dict[str, Any], list[str]]:
    """API principal de este módulo para los mappers atómicos.

    Convierte `element_styles` y decide automáticamente si emite **inline**
    o registra una **globalClass**:

    - Si tras la conversión hay <`GLOBAL_CLASS_MIN_PROPS` keys → inline.
    - Si hay ≥ threshold → globalClass nueva (o reusa si misma settings).

    Devuelve `(inline_settings, css_global_classes_list)` donde:
    - `inline_settings`: dict para mezclar con los settings base del elemento
    - `css_global_classes_list`: lista de strings para meter en
      `settings._cssGlobalClasses` (puede estar vacía).
    """
    converted = _styles_to_bricks_settings(element_styles, ctx)
    if not converted:
        return {}, []

    # Contar "propiedades efectivas" — keys top-level + sub-keys de
    # _typography/_padding/_background.
    prop_count = 0
    for v in converted.values():
        if isinstance(v, dict):
            prop_count += len(v)
        else:
            prop_count += 1

    if prop_count < GLOBAL_CLASS_MIN_PROPS:
        return converted, []

    class_name = _get_or_create_global_class(converted, prefix=prefix, ctx=ctx)
    return {}, [class_name]


__all__ = [
    "styles_inline_or_class",
    "_styles_to_bricks_settings",
    "_get_or_create_global_class",
    "GLOBAL_CLASS_MIN_PROPS",
]
