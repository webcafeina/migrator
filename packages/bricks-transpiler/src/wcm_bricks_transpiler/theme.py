"""Construcción de Theme Styles globales.

Estrategia MVP:
- Si el proyecto define `theme_styles_origin` (clusters de color extraídos
  por content-extractor o el operador), usarlos directamente.
- Si no, usar la paleta de marca Webcafeína por defecto (paleta corporativa
  que el cliente puede reemplazar después en wp-admin > Bricks > Theme Styles).

En todos los casos, el preset Webcafeína sirve como fallback razonable: oscuro,
acento lima, tipografía sans-serif legible.

G.6 (2026-05-21) — los mappers atomic/composite usan `var(--bricks-color-<id>)`
para colores (NO `var(--<name>)`) porque ese es el formato real que Bricks
2.3.5 genera en `:root` desde `colorPalette`. Si los mappers usaran
`var(--primary)` directamente, no resolvería (CSS var no definida en root).
"""

from __future__ import annotations

import re
from typing import Any

from wcm_bricks_transpiler.schema import (
    DEFAULT_BREAKPOINTS,
    BricksColorEntry,
    BricksThemeStyles,
    BricksThemeStylesEntry,
)


def _slugify_color_id(name: str) -> str:
    """`"Detail Brown"` → `"detail-brown"`. Solo a-z0-9-, sin acentos."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return s.strip("-") or "color"


#: Paleta Webcafeína (CLAUDE.md §3). Usada como default si el origen no aporta colores.
DEFAULT_PALETTE: list[BricksColorEntry] = [
    BricksColorEntry(id="primary", name="Primary", raw="#171009"),
    BricksColorEntry(id="secondary", name="Secondary", raw="#2B1A0E"),
    BricksColorEntry(id="text", name="Text", raw="#F2E8D2"),
    BricksColorEntry(id="accent", name="Accent", raw="#B1F100"),
    BricksColorEntry(id="detail-brown", name="Detail Brown", raw="#5A3519"),
]


def build_theme_styles(
    theme_styles_origin: dict[str, Any] | None = None,
    *,
    style_id: str = "webcafeina-default",
    style_label: str = "Webcafeína Default",
) -> BricksThemeStyles:
    """Construye Theme Styles a partir de los hints del origen.

    Soporta dos formatos en `theme_styles_origin` (`projects.theme_styles_origin`):

    - **C.3 (2026-05-21, actual)** — `ThemeStylesAgent` desde computed styles:
        ``{"colors": {"primary","bg","text","accent"}, "typography":
        {"h1","h2","body","button"}, "spacing": {...}}``
    - **Legacy (v0.19.0)** — clusters de color por content-extractor:
        ``{"colors": [{"name","color"}, ...], "typography":
        {"body_font_family","heading_font_family"}}``

    Si está vacío o None → paleta Webcafeína corporativa por defecto.
    """
    palette: list[BricksColorEntry] = list(DEFAULT_PALETTE)
    typography_hints: dict[str, Any] = {}

    if theme_styles_origin:
        origin_colors = theme_styles_origin.get("colors")
        if isinstance(origin_colors, dict):
            # C.3 — colors es {name: hex}. El id coincide con el name
            # slugificado para que `var(--bricks-color-primary)` resuelva
            # en los mappers.
            palette = [
                BricksColorEntry(
                    id=_slugify_color_id(name),
                    name=name.capitalize(),
                    raw=hex_,
                )
                for name, hex_ in origin_colors.items()
                if isinstance(hex_, str)
            ]
        elif isinstance(origin_colors, list):
            # Legacy — lista de {name, color}. Aceptamos también {id, raw}.
            palette = []
            for c in origin_colors[:6]:
                raw = c.get("raw") or c.get("color")
                name = c.get("name") or c.get("id") or "color"
                if not isinstance(raw, str):
                    continue
                palette.append(
                    BricksColorEntry(
                        id=c.get("id") or _slugify_color_id(name),
                        name=name,
                        raw=raw,
                    )
                )
        typography_hints = theme_styles_origin.get("typography") or {}

    # Resolver fuente body/heading entre los dos formatos.
    if isinstance(typography_hints.get("body"), dict):
        body_font = typography_hints["body"].get("font-family", "Inter, sans-serif")
    else:
        body_font = typography_hints.get("body_font_family", "Inter, sans-serif")
    if isinstance(typography_hints.get("h1"), dict):
        heading_font = typography_hints["h1"].get("font-family", body_font)
    else:
        heading_font = typography_hints.get("heading_font_family", body_font)

    entry = BricksThemeStylesEntry(
        id=style_id,
        label=style_label,
        settings={
            "section": {
                "_padding": {"top": "80px", "right": "24px", "bottom": "80px", "left": "24px"},
                "_padding:mobile_portrait": {"top": "48px", "right": "16px", "bottom": "48px", "left": "16px"},
            },
            "container": {
                "_max-width": "1200px",
            },
            "heading": {
                "_typography": {
                    "font-family": heading_font,
                    "font-weight": "700",
                    "color": {"raw": "var(--bricks-color-text)"},
                },
            },
            "text": {
                "_typography": {
                    "font-family": body_font,
                    "font-size": "16px",
                    "line-height": "1.6",
                    "color": {"raw": "var(--bricks-color-text)"},
                },
            },
            "button": {
                "_background": {"color": {"raw": "var(--bricks-color-accent)"}},
                "_typography": {
                    "color": {"raw": "var(--bricks-color-primary)"},
                    "font-weight": "600",
                },
                "_padding": {"top": "12px", "right": "24px", "bottom": "12px", "left": "24px"},
                "_border": {
                    "radius": {"top": "8px", "right": "8px", "bottom": "8px", "left": "8px"}
                },
            },
        },
        conditions=[],
    )

    return BricksThemeStyles(
        theme_styles=[entry],
        colorPalette=palette,
        breakpoints=dict(DEFAULT_BREAKPOINTS),
    )
