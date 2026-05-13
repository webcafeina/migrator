"""Construcción de Theme Styles globales.

Estrategia MVP:
- Si el proyecto define `theme_styles_origin` (clusters de color extraídos
  por content-extractor o el operador), usarlos directamente.
- Si no, usar la paleta de marca Webcafeína por defecto (paleta corporativa
  que el cliente puede reemplazar después en wp-admin > Bricks > Theme Styles).

En todos los casos, el preset Webcafeína sirve como fallback razonable: oscuro,
acento lima, tipografía sans-serif legible.
"""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler.schema import (
    DEFAULT_BREAKPOINTS,
    BricksColorEntry,
    BricksThemeStyles,
    BricksThemeStylesEntry,
)

#: Paleta Webcafeína (CLAUDE.md §3). Usada como default si el origen no aporta colores.
DEFAULT_PALETTE: list[BricksColorEntry] = [
    BricksColorEntry(name="primary", color="#171009"),
    BricksColorEntry(name="secondary", color="#2B1A0E"),
    BricksColorEntry(name="text", color="#F2E8D2"),
    BricksColorEntry(name="accent", color="#B1F100"),
    BricksColorEntry(name="detail-brown", color="#5A3519"),
]


def build_theme_styles(
    theme_styles_origin: dict[str, Any] | None = None,
    *,
    style_id: str = "webcafeina-default",
    style_label: str = "Webcafeína Default",
) -> BricksThemeStyles:
    """Construye Theme Styles a partir de los hints del origen.

    `theme_styles_origin` (de `projects.theme_styles_origin`) puede contener:
    - `colors: list[{name, color}]` — paleta detectada por content-extractor
    - `typography: {body_font_family, heading_font_family, ...}`
    - `radius_base, spacing_base` — sugerencias

    Si está vacío o None, se aplica la paleta Webcafeína corporativa.
    """
    palette: list[BricksColorEntry]
    typography_hints: dict[str, Any] = {}

    if theme_styles_origin and (origin_colors := theme_styles_origin.get("colors")):
        palette = [
            BricksColorEntry(name=c["name"], color=c["color"])
            for c in origin_colors[:6]  # top-6
        ]
    else:
        palette = list(DEFAULT_PALETTE)

    if theme_styles_origin:
        typography_hints = theme_styles_origin.get("typography") or {}

    body_font = typography_hints.get("body_font_family", "Inter, sans-serif")
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
                    "color": {"raw": "var(--text)"},
                },
            },
            "text": {
                "_typography": {
                    "font-family": body_font,
                    "font-size": "var(--text-base, 16px)",
                    "line-height": "1.6",
                    "color": {"raw": "var(--text)"},
                },
            },
            "button": {
                "_background": {"color": {"raw": "var(--accent)"}},
                "_typography": {"color": {"raw": "var(--primary)"}, "font-weight": "600"},
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
