"""Tests del validador de páginas Bricks."""

from __future__ import annotations

from wcm_bricks_transpiler.validator import validate_bricks_page


def test_valid_minimal_page() -> None:
    page = [
        {
            "id": "sec001",
            "name": "section",
            "parent": "0",
            "children": ["con001"],
            "settings": {},
        },
        {
            "id": "con001",
            "name": "container",
            "parent": "sec001",
            "children": ["hed001"],
            "settings": {},
        },
        {
            "id": "hed001",
            "name": "heading",
            "parent": "con001",
            "children": [],
            "settings": {"tag": "h1", "text": "Hola"},
        },
    ]
    result = validate_bricks_page(page)
    assert result.is_valid, f"Errores inesperados: {result.errors}"


def test_duplicate_id_detected() -> None:
    page = [
        {"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}},
        {"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "duplicate_id" in codes


def test_orphan_parent_detected() -> None:
    page = [
        {"id": "abc001", "name": "container", "parent": "xyz999", "children": [], "settings": {}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "orphan_parent" in codes


def test_nested_section_emits_warning_not_error() -> None:
    """v0.27.0 — Bricks acepta nested sections (poco común). Modelos IA
    a veces las generan. Degradado a warning, no bloquea is_valid."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["sec002"], "settings": {}},
        {"id": "sec002", "name": "section", "parent": "sec001", "children": [], "settings": {}},
    ]
    result = validate_bricks_page(page)
    error_codes = [i.code for i in result.errors]
    warning_codes = [i.code for i in result.warnings]
    assert "top_level_with_parent" not in error_codes
    assert "nested_section" in warning_codes
    assert result.is_valid  # warnings no bloquean


def test_atomic_with_children_rejected() -> None:
    page = [
        {
            "id": "hed001",
            "name": "heading",
            "parent": "0",
            "children": ["xyz001"],
            "settings": {"tag": "h1", "text": "x"},
        },
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "atomic_with_children" in codes


def test_parent_child_inconsistency_detected() -> None:
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": [], "settings": {}},
        {"id": "con001", "name": "container", "parent": "sec001", "children": [], "settings": {}},
    ]
    # con001 dice ser hijo de sec001, pero sec001.children=[] no lo lista.
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "parent_child_inconsistent" in codes


def test_invalid_id_format_rejected() -> None:
    page = [
        {"id": "ABC123", "name": "section", "parent": "0", "children": [], "settings": {}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "invalid_id_format" in codes


def test_parent_all_digits_aceptado() -> None:
    """Bug 2026-05-21 (proyecto 20): `make_element_id` puede devolver
    un hash de 6 chars que sea TODO dígitos (p.ej. "815892"). El
    validador anterior usaba `.islower()` que devuelve False para
    strings sin letras → rechazaba ~6% de los IDs generados.
    """
    from wcm_bricks_transpiler.schema import BricksElement

    # `parent` todo dígitos debe aceptarse (es un ID hex válido).
    el = BricksElement(
        id="abc001", name="container", parent="815892", children=[], settings={}
    )
    assert el.parent == "815892"

    # `id` todo dígitos también — el Field(pattern=...) usa regex propio.
    el2 = BricksElement(
        id="123456", name="block", parent="0", children=[], settings={}
    )
    assert el2.id == "123456"


def test_unsupported_name_rejected() -> None:
    page = [
        {"id": "abc001", "name": "carousel-xyz", "parent": "0", "children": [], "settings": {}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "unsupported_element_name" in codes


# -----------------------------------------------------------------------------
# v0.28.0 — Settings shape validation (Bricks 2.1.4 verbatim)
# Bug raíz del E2E v0.27.0 (mariya.design): typography keys con underscore
# eran ignoradas por Bricks → render con CSS default (texto plano sin estilos).
# -----------------------------------------------------------------------------


def _wrap(settings_dict: dict, name: str = "heading") -> list:
    """Helper: envuelve un settings dict en un page mínimo válido en
    estructura, así los tests aíslan la validación del shape de settings."""
    base_settings = {"text": "x", "tag": "h1"} if name == "heading" else {}
    base_settings.update(settings_dict)
    return [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["xxx001"], "settings": {}},
        {"id": "xxx001", "name": name, "parent": "sec001", "children": [], "settings": base_settings},
    ]


def test_typography_underscore_key_rejected() -> None:
    """Bug raíz: `font_size` en lugar de `font-size`."""
    result = validate_bricks_page(_wrap({"_typography": {"font_size": "2rem"}}))
    codes = [i.code for i in result.errors]
    assert "typography_underscore_key" in codes


def test_typography_camelcase_key_rejected() -> None:
    """Bug raíz alt: `fontSize` (camelCase) en lugar de `font-size`."""
    result = validate_bricks_page(_wrap({"_typography": {"fontSize": "2rem"}}))
    codes = [i.code for i in result.errors]
    assert "typography_camelcase_key" in codes


def test_typography_kebab_case_accepted() -> None:
    """Happy path: kebab-case válido."""
    result = validate_bricks_page(_wrap({
        "_typography": {
            "font-size": "2rem",
            "font-family": "Inter",
            "font-weight": "700",
            "line-height": "1.2",
            "color": {"raw": "var(--bricks-color-text)"},
        }
    }))
    # No errores relacionados con typography shape
    typo_errs = [i for i in result.errors if i.code.startswith("typography_")]
    assert typo_errs == []


def test_spacing_shorthand_string_rejected() -> None:
    """`_padding: '4rem'` (string) en lugar de objeto."""
    result = validate_bricks_page(_wrap({"_padding": "4rem"}))
    codes = [i.code for i in result.errors]
    assert "spacing_shorthand_string" in codes


def test_spacing_object_shape_accepted() -> None:
    result = validate_bricks_page(_wrap({
        "_padding": {"top": "4rem", "right": "1rem", "bottom": "4rem", "left": "1rem"}
    }))
    sp_errs = [i for i in result.errors if i.code.startswith("spacing_")]
    assert sp_errs == []


def test_color_string_rejected() -> None:
    """`color: '#000'` en lugar de `{hex: '#000'}`."""
    result = validate_bricks_page(_wrap({"_typography": {"color": "#000"}}))
    codes = [i.code for i in result.errors]
    assert "color_string_not_object" in codes


def test_color_hex_object_accepted() -> None:
    result = validate_bricks_page(_wrap({"_typography": {"color": {"hex": "#000000"}}}))
    color_errs = [i for i in result.errors if i.code.startswith("color_")]
    assert color_errs == []


def test_background_image_string_rejected() -> None:
    """`_background.image: 'url'` (string) en lugar de objeto."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": [],
         "settings": {"_background": {"image": "https://x.jpg"}}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "background_image_string" in codes


def test_image_element_string_rejected() -> None:
    """Elemento `image` con `image: '<url>'` plano."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["img001"], "settings": {}},
        {"id": "img001", "name": "image", "parent": "sec001", "children": [],
         "settings": {"image": "https://oai.example/x.jpg"}},
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    assert "image_element_string" in codes


def test_image_external_accepted_without_wp_id() -> None:
    """Image con external=true no requiere id WP."""
    page = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["img001"], "settings": {}},
        {"id": "img001", "name": "image", "parent": "sec001", "children": [],
         "settings": {"image": {"url": "https://x.jpg", "external": True, "filename": "x.jpg"}}},
    ]
    result = validate_bricks_page(page)
    img_errs = [i for i in result.errors if i.code.startswith("image_")]
    assert img_errs == []


def test_global_classes_object_items_rejected() -> None:
    """`_cssGlobalClasses: [{id, name}]` en lugar de strings."""
    result = validate_bricks_page(_wrap({
        "_cssGlobalClasses": [{"id": "x", "name": "btn"}],
    }))
    codes = [i.code for i in result.errors]
    assert "global_classes_object_item" in codes


def test_global_classes_strings_accepted() -> None:
    result = validate_bricks_page(_wrap({"_cssGlobalClasses": ["btn", "btn-primary"]}))
    gc_errs = [i for i in result.errors if i.code.startswith("global_classes_")]
    assert gc_errs == []


def test_real_world_e2e_v027_bug_reproduced() -> None:
    """Reproduce el bug exacto del E2E v0.27.0 con mariya.design.
    El heading completo del home generado por gpt-5-mini, sin BricksAdapter,
    es ignorado por Bricks frontend (CSS default, sin Playfair, sin tamaño,
    sin colores). El validator de v0.28.0 debe detectarlo."""
    home_heading = {
        "id": "j1k2l3",
        "name": "heading",
        "parent": "d4e5f6",
        "children": [],
        "settings": {
            "text": "Brand Identity Systems forPremium andLuxury-LedBrands",
            "tag": "h1",
            "_typography": {
                "color": {"raw": "var(--bricks-color-text)"},
                "font_size": "2.25rem",     # ← BUG (underscore)
                "font_family": "Playfair Display",  # ← BUG (underscore)
                "line_height": "1.2",       # ← BUG (underscore)
            },
        },
    }
    page = [
        {"id": "a1b2c3", "name": "section", "parent": "0", "children": ["d4e5f6"], "settings": {}},
        {"id": "d4e5f6", "name": "container", "parent": "a1b2c3", "children": ["j1k2l3"], "settings": {}},
        home_heading,
    ]
    result = validate_bricks_page(page)
    codes = [i.code for i in result.errors]
    # 3 underscore_key errors (font_size, font_family, line_height)
    assert codes.count("typography_underscore_key") == 3
    assert not result.is_valid
