"""Tests del builder de Theme Styles."""

from __future__ import annotations

from wcm_bricks_transpiler.theme import build_theme_styles


def test_default_palette_is_webcafeina() -> None:
    """G.6 (2026-05-21) — paleta default usa shape Bricks `{id, name, raw}`."""
    ts = build_theme_styles(None)
    assert len(ts.colorPalette) == 5
    ids = [c.id for c in ts.colorPalette]
    assert ids == ["primary", "secondary", "text", "accent", "detail-brown"]
    accent = next(c for c in ts.colorPalette if c.id == "accent")
    assert accent.raw == "#B1F100"  # accent lima


def test_custom_palette_from_origin_truncates_to_six() -> None:
    origin = {
        "colors": [
            {"name": f"c{i}", "color": f"#{i:06x}"} for i in range(10)
        ],
    }
    ts = build_theme_styles(origin)
    assert len(ts.colorPalette) == 6


def test_breakpoints_default_to_bricks_2_standard() -> None:
    ts = build_theme_styles(None)
    assert ts.breakpoints == {
        "desktop": 992,
        "tablet_portrait": 991,
        "mobile_landscape": 767,
        "mobile_portrait": 478,
    }


def test_theme_style_entry_has_section_button_heading_text() -> None:
    ts = build_theme_styles(None)
    entry = ts.theme_styles[0]
    assert "section" in entry.settings
    assert "button" in entry.settings
    assert "heading" in entry.settings
    assert "text" in entry.settings


def test_typography_hints_propagate() -> None:
    ts = build_theme_styles({"typography": {"body_font_family": "Poppins, sans-serif"}})
    entry = ts.theme_styles[0]
    assert entry.settings["text"]["_typography"]["font-family"] == "Poppins, sans-serif"


# C.3+C.6 (2026-05-21) — formato nuevo de ThemeStylesAgent:
# colors es dict {primary,bg,text,accent} y typography es dict de dicts.


def test_c3_format_colors_dict() -> None:
    """colors como dict {name: hex} se convierte en N entries `{id, name, raw}`.

    G.6 (2026-05-21) — el id es el slug del name (lowercase, espacios →
    guiones) para que `var(--bricks-color-<id>)` resuelva en los mappers.
    """
    origin = {
        "colors": {
            "primary": "#000000",
            "bg": "#ffffff",
            "text": "#141414",
            "accent": "#b1f100",
        }
    }
    ts = build_theme_styles(origin)
    ids = {c.id for c in ts.colorPalette}
    assert ids == {"primary", "bg", "text", "accent"}
    accent = next(c for c in ts.colorPalette if c.id == "accent")
    assert accent.raw == "#b1f100"
    # El name viene capitalizado (label legible en editor).
    assert accent.name == "Accent"


def test_c3_format_typography_dict_de_dicts() -> None:
    """typography.body.font-family / typography.h1.font-family se mapean
    a body_font / heading_font del Theme Styles entry."""
    origin = {
        "typography": {
            "body": {"font-family": "Inter, sans-serif", "font-size": "16px"},
            "h1": {"font-family": "Playfair Display", "font-size": "64px"},
        }
    }
    ts = build_theme_styles(origin)
    entry = ts.theme_styles[0]
    assert entry.settings["text"]["_typography"]["font-family"] == "Inter, sans-serif"
    assert entry.settings["heading"]["_typography"]["font-family"] == "Playfair Display"


def test_c3_format_completo_no_pierde_palette_si_no_colors() -> None:
    """Si origin no aporta colors, la paleta default sigue activa."""
    ts = build_theme_styles({"typography": {"body": {"font-family": "Roboto"}}})
    assert len(ts.colorPalette) == 5  # default Webcafeína


# G.7 — Google Fonts loader vía customCode.headerScripts.


def test_g7_sin_google_fonts_no_emite_custom_code() -> None:
    """Sin google_fonts en origen → customCode queda vacío."""
    ts = build_theme_styles({"colors": {"primary": "#000"}})
    d = ts.model_dump(by_alias=True)
    # customCode debe estar pero vacío (no emite link).
    assert d.get("customCode") == {}


def test_g7_emite_link_google_fonts_en_header_scripts() -> None:
    """google_fonts=['Inter','Playfair Display'] → customCode.headerScripts
    contiene <link href='fonts.googleapis.com/css2?family=Inter:...&family=Playfair+Display:...'>"""
    ts = build_theme_styles({"google_fonts": ["Inter", "Playfair Display"]})
    d = ts.model_dump(by_alias=True)
    link = d["customCode"]["headerScripts"]
    assert "fonts.googleapis.com/css2" in link
    assert "family=Inter:" in link
    assert "family=Playfair+Display:" in link
    assert "display=swap" in link
    assert "preconnect" in link  # preconnect tags incluidos


def test_g7_ignora_entries_no_string() -> None:
    """Defensive: si llega `google_fonts` con None o ints, se ignoran."""
    ts = build_theme_styles({"google_fonts": ["Inter", None, 42, "", "Roboto"]})
    d = ts.model_dump(by_alias=True)
    link = d["customCode"]["headerScripts"]
    assert "family=Inter:" in link
    assert "family=Roboto:" in link
    assert "family=None" not in link
    assert "family=42" not in link
