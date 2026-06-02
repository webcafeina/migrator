"""Tests del BricksAdapter (v0.28.0 B2).

Verifica que el adapter convierte correctamente los 6 anti-patrones
detectados durante el E2E v0.27.0 al shape Bricks 2.1.4 verbatim, y que
el output siempre pasa el validator B1.
"""

from __future__ import annotations

from wcm_bricks_transpiler.bricks_adapter import (
    AdapterStats,
    adapt_to_bricks_native,
)
from wcm_bricks_transpiler.validator import validate_bricks_page


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _wrap_settings(name: str, settings: dict) -> list[dict]:
    base = {"text": "x", "tag": "h1"} if name == "heading" else {}
    base.update(settings)
    return [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["xxx001"], "settings": {}},
        {"id": "xxx001", "name": name, "parent": "sec001", "children": [], "settings": base},
    ]


def _settings_of(adapted: list[dict], element_id: str) -> dict:
    for el in adapted:
        if el["id"] == element_id:
            return el["settings"]
    raise AssertionError(f"Elemento {element_id} no encontrado")


# -----------------------------------------------------------------------------
# 1. Typography keys: snake → kebab / camel → kebab
# -----------------------------------------------------------------------------


def test_typography_snake_to_kebab() -> None:
    page = _wrap_settings("heading", {
        "_typography": {
            "font_size": "2rem",
            "font_family": "Inter",
            "line_height": "1.2",
            "color": {"raw": "var(--text)"},
        }
    })
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert "font-size" in typo
    assert "font-family" in typo
    assert "line-height" in typo
    assert typo["font-size"] == "2rem"
    assert typo["color"] == {"raw": "var(--text)"}
    assert stats.typography_keys_fixed == 3
    # Output debe pasar el validator
    assert validate_bricks_page(out).is_valid


def test_typography_camel_to_kebab() -> None:
    page = _wrap_settings("heading", {
        "_typography": {
            "fontSize": "2rem",
            "fontFamily": "Inter",
            "lineHeight": "1.2",
        }
    })
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert "font-size" in typo
    assert "font-family" in typo
    assert "line-height" in typo
    assert stats.typography_keys_fixed == 3
    assert validate_bricks_page(out).is_valid


def test_typography_kebab_idempotent() -> None:
    """Input ya correcto no debe cambiar."""
    page = _wrap_settings("heading", {
        "_typography": {"font-size": "2rem", "font-family": "Inter"}
    })
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert typo == {"font-size": "2rem", "font-family": "Inter"}
    assert stats.typography_keys_fixed == 0


def test_typography_unknown_key_preserved() -> None:
    """Keys no en el catálogo se preservan (no perdemos data del LLM)."""
    page = _wrap_settings("heading", {
        "_typography": {"font-size": "2rem", "weirdKey": "x"}
    })
    out = adapt_to_bricks_native(page)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert "weirdKey" in typo


# -----------------------------------------------------------------------------
# 2. Spacing shorthand string → objeto {top, right, bottom, left}
# -----------------------------------------------------------------------------


def test_padding_one_value_expanded() -> None:
    page = _wrap_settings("heading", {"_padding": "4rem"})
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    p = _settings_of(out, "xxx001")["_padding"]
    assert p == {"top": "4rem", "right": "4rem", "bottom": "4rem", "left": "4rem"}
    assert stats.spacing_expanded == 1
    assert validate_bricks_page(out).is_valid


def test_padding_two_values_expanded() -> None:
    page = _wrap_settings("heading", {"_padding": "4rem 1rem"})
    out = adapt_to_bricks_native(page)
    p = _settings_of(out, "xxx001")["_padding"]
    assert p == {"top": "4rem", "right": "1rem", "bottom": "4rem", "left": "1rem"}


def test_padding_four_values_expanded() -> None:
    page = _wrap_settings("heading", {"_padding": "1rem 2rem 3rem 4rem"})
    out = adapt_to_bricks_native(page)
    p = _settings_of(out, "xxx001")["_padding"]
    assert p == {"top": "1rem", "right": "2rem", "bottom": "3rem", "left": "4rem"}


def test_margin_object_preserved() -> None:
    """Objeto ya correcto no se toca."""
    orig = {"top": "1rem", "right": "0", "bottom": "1rem", "left": "0"}
    page = _wrap_settings("heading", {"_margin": orig})
    out = adapt_to_bricks_native(page)
    assert _settings_of(out, "xxx001")["_margin"] == orig


# -----------------------------------------------------------------------------
# 3. Color string → objeto {hex|raw}
# -----------------------------------------------------------------------------


def test_color_hex_string_wrapped() -> None:
    page = _wrap_settings("heading", {"_typography": {"color": "#000000"}})
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert typo["color"] == {"hex": "#000000"}
    assert stats.color_wrapped == 1


def test_color_css_var_wrapped_as_raw() -> None:
    page = _wrap_settings("heading", {"_typography": {"color": "var(--text)"}})
    out = adapt_to_bricks_native(page)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert typo["color"] == {"raw": "var(--text)"}


def test_color_already_object_preserved() -> None:
    orig = {"hex": "#123456"}
    page = _wrap_settings("heading", {"_typography": {"color": orig}})
    out = adapt_to_bricks_native(page)
    typo = _settings_of(out, "xxx001")["_typography"]
    assert typo["color"] == orig


# -----------------------------------------------------------------------------
# 4. Image element: string URL → objeto
# -----------------------------------------------------------------------------


def test_image_string_to_external_object() -> None:
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["img001"], "settings": {}},
        {"id": "img001", "name": "image", "parent": "sec001", "children": [],
         "settings": {"image": "https://example.com/hero.jpg"}},
    ]
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    img = _settings_of(out, "img001")["image"]
    assert img["url"] == "https://example.com/hero.jpg"
    assert img["external"] is True
    assert img["filename"] == "hero.jpg"
    assert stats.image_element_wrapped == 1
    assert validate_bricks_page(out).is_valid


def test_image_string_with_wp_asset_map_injects_id() -> None:
    """Si la URL ya está subida a WP, inyectar id + full."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["img001"], "settings": {}},
        {"id": "img001", "name": "image", "parent": "sec001", "children": [],
         "settings": {"image": "https://wp.example.com/wp-content/uploads/hero.jpg"}},
    ]
    wp_map = {
        "https://wp.example.com/wp-content/uploads/hero.jpg": {
            "id": 4567,
            "filename": "hero.jpg",
            "size": "large",
            "url": "https://wp.example.com/wp-content/uploads/hero-1024.jpg",
            "full": "https://wp.example.com/wp-content/uploads/hero.jpg",
        }
    }
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, wp_asset_map=wp_map, stats=stats)
    img = _settings_of(out, "img001")["image"]
    assert img["id"] == 4567
    assert img["full"] == "https://wp.example.com/wp-content/uploads/hero.jpg"
    assert "external" not in img
    assert stats.image_wp_id_injected == 1


def test_image_object_url_in_wp_map_injects_id() -> None:
    """Image ya es dict pero sin id; lo añadimos si URL coincide."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["img001"], "settings": {}},
        {"id": "img001", "name": "image", "parent": "sec001", "children": [],
         "settings": {"image": {"url": "https://wp.example.com/x.jpg", "external": True, "filename": "x.jpg"}}},
    ]
    wp_map = {"https://wp.example.com/x.jpg": {"id": 99, "filename": "x.jpg"}}
    out = adapt_to_bricks_native(page, wp_asset_map=wp_map)
    img = _settings_of(out, "img001")["image"]
    assert img["id"] == 99
    assert "external" not in img


# -----------------------------------------------------------------------------
# 5. Background image string → objeto
# -----------------------------------------------------------------------------


def test_background_image_string_wrapped() -> None:
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": [],
         "settings": {"_background": {"image": "https://example.com/bg.jpg"}}},
    ]
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    bg = _settings_of(out, "sec001")["_background"]
    assert bg["image"] == {
        "url": "https://example.com/bg.jpg",
        "size": "cover",
        "position": "center center",
    }
    assert stats.background_image_wrapped == 1
    assert validate_bricks_page(out).is_valid


def test_background_color_string_wrapped() -> None:
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": [],
         "settings": {"_background": {"color": "#abcdef"}}},
    ]
    out = adapt_to_bricks_native(page)
    assert _settings_of(out, "sec001")["_background"]["color"] == {"hex": "#abcdef"}


# -----------------------------------------------------------------------------
# 6. _cssGlobalClasses: objetos → strings
# -----------------------------------------------------------------------------


def test_global_classes_objects_flattened_to_strings() -> None:
    page = _wrap_settings("heading", {
        "_cssGlobalClasses": [{"id": "btn", "name": "Button"}, {"id": "lg"}],
    })
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    gc = _settings_of(out, "xxx001")["_cssGlobalClasses"]
    assert gc == ["btn", "lg"]
    assert stats.global_classes_flattened == 1


def test_global_classes_strings_unchanged() -> None:
    page = _wrap_settings("heading", {"_cssGlobalClasses": ["btn", "btn-primary"]})
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, stats=stats)
    assert _settings_of(out, "xxx001")["_cssGlobalClasses"] == ["btn", "btn-primary"]
    assert stats.global_classes_flattened == 0


# -----------------------------------------------------------------------------
# Idempotencia y caso real-world
# -----------------------------------------------------------------------------


def test_adapter_idempotent() -> None:
    """Aplicar el adapter 2 veces debe dar el mismo resultado."""
    page = _wrap_settings("heading", {
        "_typography": {"font_size": "2rem"},
        "_padding": "4rem",
    })
    once = adapt_to_bricks_native(page)
    twice = adapt_to_bricks_native(once)
    assert once == twice


def test_input_not_mutated() -> None:
    """El adapter NO debe mutar el input."""
    page = _wrap_settings("heading", {"_typography": {"font_size": "2rem"}})
    before = page[1]["settings"]["_typography"].copy()
    adapt_to_bricks_native(page)
    assert page[1]["settings"]["_typography"] == before  # original intacto


def test_global_classes_filtered_against_catalog() -> None:
    """v0.28.0 B11 — Si valid_class_ids está set, IDs fuera del catálogo
    se dropean. Adapter no inventa, solo filtra."""
    page = _wrap_settings("heading", {
        "_cssGlobalClasses": ["wcm-h1", "invented-class", "wcm-body"],
    })
    valid = {"wcm-h1", "wcm-h2", "wcm-body", "wcm-btn-primary"}
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, valid_class_ids=valid, stats=stats)
    gc = _settings_of(out, "xxx001")["_cssGlobalClasses"]
    assert gc == ["wcm-h1", "wcm-body"]
    assert stats.global_classes_dropped_unknown == 1


def test_global_classes_no_filter_when_valid_ids_none() -> None:
    """Sin valid_class_ids, no se filtra (legacy behavior)."""
    page = _wrap_settings("heading", {
        "_cssGlobalClasses": ["random-1", "random-2"],
    })
    out = adapt_to_bricks_native(page, valid_class_ids=None)
    gc = _settings_of(out, "xxx001")["_cssGlobalClasses"]
    assert gc == ["random-1", "random-2"]


def test_global_classes_filter_combines_with_flatten() -> None:
    """Flatten primero, luego filter. Objects + IDs inválidas."""
    page = _wrap_settings("heading", {
        "_cssGlobalClasses": [
            {"id": "wcm-h1", "name": "H1"},
            {"id": "fake-class"},
            "wcm-body",
        ],
    })
    valid = {"wcm-h1", "wcm-body"}
    stats = AdapterStats()
    out = adapt_to_bricks_native(page, valid_class_ids=valid, stats=stats)
    gc = _settings_of(out, "xxx001")["_cssGlobalClasses"]
    assert gc == ["wcm-h1", "wcm-body"]
    assert stats.global_classes_flattened == 1
    assert stats.global_classes_dropped_unknown == 1


def test_real_world_e2e_v027_bug_fixed() -> None:
    """Reproduce el bug exacto del E2E v0.27.0 y verifica que el adapter
    lo corrige + output pasa validator."""
    home_page = [
        {"id": "a1b2c3", "name": "section", "parent": "0", "children": ["d4e5f6"],
         "settings": {
             "_padding": {"top": "4rem", "right": "1rem", "bottom": "4rem", "left": "1rem"},
             "_background": {
                 "color": {"raw": "var(--bricks-color-bg)"},
                 "image": {
                     "url": "https://static.wixstatic.com/media/f906fd_xxx.jpg",
                     "size": "cover",
                     "position": "center center",
                 },
             },
         }},
        {"id": "d4e5f6", "name": "container", "parent": "a1b2c3", "children": ["j1k2l3"],
         "settings": {"_widthMax": "1200"}},
        {"id": "j1k2l3", "name": "heading", "parent": "d4e5f6", "children": [],
         "settings": {
             "text": "Brand Identity Systems for Premium and Luxury-Led Brands",
             "tag": "h1",
             "_typography": {
                 "color": {"raw": "var(--bricks-color-text)"},
                 "font_size": "2.25rem",     # ← BUG
                 "font_family": "Playfair Display",  # ← BUG
                 "line_height": "1.2",       # ← BUG
             },
         }},
    ]
    stats = AdapterStats()
    out = adapt_to_bricks_native(home_page, stats=stats)
    # Heading ahora tiene keys kebab-case
    h_typo = _settings_of(out, "j1k2l3")["_typography"]
    assert h_typo["font-size"] == "2.25rem"
    assert h_typo["font-family"] == "Playfair Display"
    assert h_typo["line-height"] == "1.2"
    assert "font_size" not in h_typo
    assert "font_family" not in h_typo
    assert stats.typography_keys_fixed == 3
    # Y el output pasa el validator B1 al completo
    result = validate_bricks_page(out)
    assert result.is_valid, f"Errores: {[i.code for i in result.errors]}"
