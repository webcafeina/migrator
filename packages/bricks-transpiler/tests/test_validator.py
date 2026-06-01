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
