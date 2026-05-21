"""Tests del helper de conversión computed styles → Bricks settings (v0.23.0)."""

from __future__ import annotations

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.mappers._styling import (
    GLOBAL_CLASS_MIN_PROPS,
    _color_to_bricks,
    _font_family_clean,
    _parse_shorthand_four_sides,
    _styles_to_bricks_settings,
    styles_inline_or_class,
)
from wcm_bricks_transpiler.mappers._types import MapperContext


def _ctx(theme_styles=None) -> MapperContext:
    return MapperContext(
        project_id=1,
        page_id=1,
        page_lang="es",
        id_gen=IdGenerator(project_id=1, page_id=1),
        asset_resolver=lambda _id: {"url": f"/uploads/{_id}.webp"},
        theme_styles=theme_styles,
    )


# ---------- color shape ----------


def test_color_to_bricks_envuelve_en_raw() -> None:
    assert _color_to_bricks("rgb(20, 30, 40)") == {"raw": "rgb(20, 30, 40)"}


def test_color_to_bricks_matchea_palette_a_var() -> None:
    palette = {"primary": "rgb(20, 30, 40)", "accent": "#b1f100"}
    out = _color_to_bricks("rgb(20, 30, 40)", palette)
    assert out == {"raw": "var(--bricks-color-primary)"}


def test_color_to_bricks_descartes() -> None:
    assert _color_to_bricks(None) is None
    assert _color_to_bricks("") is None
    assert _color_to_bricks("transparent") is None
    assert _color_to_bricks("rgba(0, 0, 0, 0)") is None


# ---------- padding shorthand ----------


def test_parse_padding_one_value() -> None:
    assert _parse_shorthand_four_sides("16px") == {
        "top": "16px", "right": "16px", "bottom": "16px", "left": "16px"
    }


def test_parse_padding_two_values() -> None:
    assert _parse_shorthand_four_sides("12px 24px") == {
        "top": "12px", "right": "24px", "bottom": "12px", "left": "24px"
    }


def test_parse_padding_four_values() -> None:
    assert _parse_shorthand_four_sides("4px 8px 12px 16px") == {
        "top": "4px", "right": "8px", "bottom": "12px", "left": "16px"
    }


def test_parse_padding_zero_devuelve_none() -> None:
    assert _parse_shorthand_four_sides("0") is None
    assert _parse_shorthand_four_sides("0px") is None


# ---------- font family clean ----------


def test_font_family_clean_extrae_primera() -> None:
    assert _font_family_clean('"Albra Sans", Helvetica, sans-serif') == "Albra Sans"


def test_font_family_clean_filtra_wfont_aliases() -> None:
    # Si todas son aliases internas Wix + system, devuelve None.
    assert _font_family_clean('wfont_8a3, wf_albra, sans-serif') is None


def test_font_family_clean_salta_generics() -> None:
    assert _font_family_clean("sans-serif, serif") is None


# ---------- _styles_to_bricks_settings end-to-end ----------


def test_styles_to_bricks_typography_completo() -> None:
    ctx = _ctx()
    out = _styles_to_bricks_settings(
        {
            "color": "rgb(20, 30, 40)",
            "font-family": '"Albra Sans", sans-serif',
            "font-size": "32px",
            "font-weight": "700",
            "line-height": "1.2",
            "letter-spacing": "0.5px",
            "text-align": "center",
        },
        ctx,
    )
    typo = out["_typography"]
    assert typo["color"] == {"raw": "rgb(20, 30, 40)"}
    assert typo["font-family"] == "Albra Sans"
    assert typo["font-size"] == "32px"
    assert typo["font-weight"] == "700"
    assert typo["line-height"] == "1.2"
    assert typo["letter-spacing"] == "0.5px"
    assert typo["text-align"] == "center"


def test_styles_to_bricks_omite_defaults() -> None:
    # font-weight: normal/400 → no se incluye.
    out = _styles_to_bricks_settings({"font-weight": "400"}, _ctx())
    assert "_typography" not in out


def test_styles_to_bricks_background_url() -> None:
    out = _styles_to_bricks_settings(
        {"background-image": 'url("https://cdn.example.com/img.png")'},
        _ctx(),
    )
    assert out["_background"]["image"]["url"] == "https://cdn.example.com/img.png"


def test_styles_to_bricks_background_gradient() -> None:
    grad = "linear-gradient(180deg, rgb(0,0,0) 0%, rgb(255,255,255) 100%)"
    out = _styles_to_bricks_settings({"background-image": grad}, _ctx())
    assert out["_background"]["_gradient"] == grad


def test_styles_to_bricks_padding() -> None:
    out = _styles_to_bricks_settings({"padding": "16px 32px"}, _ctx())
    assert out["_padding"] == {
        "top": "16px", "right": "32px", "bottom": "16px", "left": "32px"
    }


def test_styles_to_bricks_border_radius() -> None:
    out = _styles_to_bricks_settings({"border-radius": "8px"}, _ctx())
    assert out["_border"]["radius"]["top"] == "8px"


# ---------- styles_inline_or_class ----------


def test_inline_si_styling_minimo() -> None:
    """Solo 1-2 propiedades → inline, sin globalClass."""
    ctx = _ctx()
    inline, classes = styles_inline_or_class(
        {"font-weight": "700"},
        prefix="h2", ctx=ctx,
    )
    assert classes == []
    assert ctx.global_classes == []
    assert inline == {"_typography": {"font-weight": "700"}}


def test_global_class_si_styling_rico() -> None:
    """≥THRESHOLD propiedades → globalClass, dedup automática por digest."""
    ctx = _ctx()
    es = {
        "color": "rgb(20, 30, 40)",
        "font-family": "Albra Sans",
        "font-size": "32px",
        "font-weight": "700",
        "padding": "16px 24px",
    }
    inline1, classes1 = styles_inline_or_class(es, prefix="h2", ctx=ctx)
    inline2, classes2 = styles_inline_or_class(es, prefix="h2", ctx=ctx)
    assert inline1 == {}
    assert inline2 == {}
    assert len(classes1) == 1
    assert classes1 == classes2  # mismo settings → mismo class id
    assert len(ctx.global_classes) == 1
    entry = ctx.global_classes[0]
    assert entry["id"] == classes1[0]
    assert entry["name"] == classes1[0]
    assert entry["settings"]["_typography"]["color"] == {"raw": "rgb(20, 30, 40)"}


def test_global_class_settings_distintos_dan_ids_distintos() -> None:
    ctx = _ctx()
    es1 = {"color": "rgb(0,0,0)", "font-size": "32px", "padding": "16px"}
    es2 = {"color": "rgb(255,0,0)", "font-size": "32px", "padding": "16px"}
    _, c1 = styles_inline_or_class(es1, prefix="h2", ctx=ctx)
    _, c2 = styles_inline_or_class(es2, prefix="h2", ctx=ctx)
    assert c1 != c2
    assert len(ctx.global_classes) == 2


def test_threshold_es_3_props() -> None:
    """Sanity check del threshold actual."""
    assert GLOBAL_CLASS_MIN_PROPS == 3
