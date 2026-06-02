"""Catálogo canónico de Bricks Global Classes (v0.28.0 B11 / sub-B.3).

Genera ~10 clases globales fijas derivadas del `Project.theme_styles_origin`.
Estas clases se persisten en `Project.bricks_global_classes` y se inyectan
al WP destino vía `wp_deployer`.

El RedesignAIAgent las anuncia al LLM en el system prompt como **catálogo
cerrado**: el LLM puede referenciarlas vía `_cssGlobalClasses: ["wcm-h1"]`
pero NO inventar IDs nuevos. El BricksAdapter filtra cualquier referencia
fuera del catálogo.

Decisión arquitectónica:
- IDs deterministas (`wcm-h1`, `wcm-btn-primary`) en lugar del hash que usa
  el transpiler original (`wcm-h1-abc123`). Predecibles, legibles en Bricks
  Editor, estables entre proyectos.
- Fallbacks razonables cuando el theme no tiene un slot (ej. h3 no scrapeado
  → fallback a h2 con 80% size).
- Solo typography + spacing por clase. Color va en `_typography.color` o
  `_background.color` aparte (no clase semántica por color).
"""

from __future__ import annotations

from typing import Any

#: IDs canónicos. Lista cerrada — el LLM solo puede usar estos.
CANONICAL_CLASS_IDS: tuple[str, ...] = (
    "wcm-h1",
    "wcm-h2",
    "wcm-h3",
    "wcm-h4",
    "wcm-body",
    "wcm-body-large",
    "wcm-body-small",
    "wcm-btn-primary",
    "wcm-btn-secondary",
    "wcm-btn-outline",
    "wcm-section-padding-lg",
    "wcm-section-padding-md",
)

#: Descripción human-readable por clase, inyectada al system prompt LLM.
CLASS_DESCRIPTIONS: dict[str, str] = {
    "wcm-h1": "Heading H1 principal (hero, page title)",
    "wcm-h2": "Heading H2 (sección title)",
    "wcm-h3": "Heading H3 (subsección)",
    "wcm-h4": "Heading H4 (card title, etc.)",
    "wcm-body": "Texto cuerpo estándar",
    "wcm-body-large": "Texto cuerpo grande (lead paragraph)",
    "wcm-body-small": "Texto cuerpo pequeño (captions, footer)",
    "wcm-btn-primary": "Botón CTA principal (relleno color primary)",
    "wcm-btn-secondary": "Botón CTA secundario (relleno color secondary)",
    "wcm-btn-outline": "Botón outline (sin fondo, borde primary)",
    "wcm-section-padding-lg": "Padding generoso para hero/secciones grandes",
    "wcm-section-padding-md": "Padding estándar para secciones intermedias",
}


def build_canonical_catalog(
    theme_styles_origin: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Devuelve la lista de Bricks Global Classes lista para persistir.

    Cada entrada con shape exacto que `wp_deployer` envía al WP destino:
        {"id": "<canonical_id>", "name": "<canonical_id>", "settings": {...}}

    `theme_styles_origin` es lo que produce `ThemeStylesAgent.synthesize_theme`.
    Si None, usa defaults razonables.
    """
    theme = theme_styles_origin or {}
    typo = theme.get("typography") or {}
    h1 = typo.get("h1") or {}
    h2 = typo.get("h2") or {}
    body = typo.get("body") or {}
    button = typo.get("button") or {}

    primary = "var(--bricks-color-primary)"
    secondary = "var(--bricks-color-secondary)"
    text_color = "var(--bricks-color-text)"
    light_color = "var(--bricks-color-bg)"

    classes: list[dict[str, Any]] = []

    # ---------- Headings ----------
    classes.append(_make_class("wcm-h1", {
        "_typography": _typography_from_slot(
            h1,
            defaults={"font-size": "2.5rem", "font-weight": "700", "line-height": "1.2"},
            color={"raw": text_color},
        ),
    }))
    classes.append(_make_class("wcm-h2", {
        "_typography": _typography_from_slot(
            h2,
            defaults={"font-size": "2rem", "font-weight": "700", "line-height": "1.25"},
            color={"raw": text_color},
        ),
    }))
    # h3/h4 derivados de h2 con escala 0.8/0.65
    h3_size = _scale_size(h2.get("font-size") or "2rem", 0.8, default="1.5rem")
    h4_size = _scale_size(h2.get("font-size") or "2rem", 0.65, default="1.25rem")
    classes.append(_make_class("wcm-h3", {
        "_typography": {
            "font-family": h2.get("font-family") or h1.get("font-family") or "inherit",
            "font-size": h3_size,
            "font-weight": "600",
            "line-height": "1.3",
            "color": {"raw": text_color},
        },
    }))
    classes.append(_make_class("wcm-h4", {
        "_typography": {
            "font-family": h2.get("font-family") or h1.get("font-family") or "inherit",
            "font-size": h4_size,
            "font-weight": "600",
            "line-height": "1.35",
            "color": {"raw": text_color},
        },
    }))

    # ---------- Body ----------
    body_size = body.get("font-size") or "1rem"
    classes.append(_make_class("wcm-body", {
        "_typography": _typography_from_slot(
            body,
            defaults={"font-size": body_size, "font-weight": "400", "line-height": "1.6"},
            color={"raw": text_color},
        ),
    }))
    classes.append(_make_class("wcm-body-large", {
        "_typography": {
            "font-family": body.get("font-family") or "inherit",
            "font-size": _scale_size(body_size, 1.25, default="1.25rem"),
            "font-weight": "400",
            "line-height": "1.6",
            "color": {"raw": text_color},
        },
    }))
    classes.append(_make_class("wcm-body-small", {
        "_typography": {
            "font-family": body.get("font-family") or "inherit",
            "font-size": _scale_size(body_size, 0.875, default="0.875rem"),
            "font-weight": "400",
            "line-height": "1.5",
            "color": {"raw": text_color},
        },
    }))

    # ---------- Buttons ----------
    btn_font = button.get("font-family") or body.get("font-family") or "inherit"
    btn_size = button.get("font-size") or "1rem"
    btn_padding = {"top": "0.75rem", "right": "1.5rem", "bottom": "0.75rem", "left": "1.5rem"}
    btn_radius = {"top": "6", "right": "6", "bottom": "6", "left": "6"}
    classes.append(_make_class("wcm-btn-primary", {
        "_typography": {
            "font-family": btn_font, "font-size": btn_size, "font-weight": "600",
            "color": {"raw": light_color},
        },
        "_padding": btn_padding,
        "_background": {"color": {"raw": primary}},
        "_border": {"radius": btn_radius},
    }))
    classes.append(_make_class("wcm-btn-secondary", {
        "_typography": {
            "font-family": btn_font, "font-size": btn_size, "font-weight": "600",
            "color": {"raw": light_color},
        },
        "_padding": btn_padding,
        "_background": {"color": {"raw": secondary}},
        "_border": {"radius": btn_radius},
    }))
    classes.append(_make_class("wcm-btn-outline", {
        "_typography": {
            "font-family": btn_font, "font-size": btn_size, "font-weight": "600",
            "color": {"raw": primary},
        },
        "_padding": btn_padding,
        "_border": {
            "width": {"top": "2", "right": "2", "bottom": "2", "left": "2"},
            "style": "solid",
            "color": {"raw": primary},
            "radius": btn_radius,
        },
    }))

    # ---------- Section spacings ----------
    spacing = theme.get("spacing") or {}
    section_y = spacing.get("section_y") or "5rem"
    classes.append(_make_class("wcm-section-padding-lg", {
        "_padding": {
            "top": _scale_size(section_y, 1.5, default="6rem"),
            "right": "1.5rem",
            "bottom": _scale_size(section_y, 1.5, default="6rem"),
            "left": "1.5rem",
        },
    }))
    classes.append(_make_class("wcm-section-padding-md", {
        "_padding": {
            "top": section_y,
            "right": "1rem",
            "bottom": section_y,
            "left": "1rem",
        },
    }))

    return classes


def list_canonical_ids() -> tuple[str, ...]:
    """Devuelve los IDs canónicos. Útil para el prompt LLM y el validator."""
    return CANONICAL_CLASS_IDS


# ---------- helpers privados ----------


def _make_class(class_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    return {"id": class_id, "name": class_id, "settings": settings}


def _typography_from_slot(
    slot: dict[str, str] | None,
    *,
    defaults: dict[str, str],
    color: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construye un `_typography` desde un slot del theme con fallbacks."""
    slot = slot or {}
    out: dict[str, Any] = {}
    for key in ("font-family", "font-size", "font-weight", "line-height", "letter-spacing", "text-transform"):
        val = slot.get(key) or defaults.get(key)
        if val:
            out[key] = val
    if color is not None:
        out["color"] = color
    return out


def _scale_size(size_str: str, factor: float, *, default: str) -> str:
    """Escala una CSS size string (`1rem`, `16px`, `1.25em`) por un factor.
    Si no parsea, devuelve `default`. Preserva la unidad original."""
    if not isinstance(size_str, str):
        return default
    s = size_str.strip()
    # Extraer parte numérica + unidad
    num_part = ""
    unit_part = ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            num_part += ch
        else:
            unit_part = s[len(num_part):].strip()
            break
    if not num_part:
        return default
    try:
        val = float(num_part) * factor
    except ValueError:
        return default
    unit = unit_part or "rem"
    # Formato sin decimales redundantes
    if val == int(val):
        return f"{int(val)}{unit}"
    return f"{val:.3g}{unit}"
