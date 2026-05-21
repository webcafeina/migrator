"""Tests de los mappers RAW.1 + RAW.2 — BlockType.AI_GENERATED + RAW_HTML.

Sprint v0.22.0.
"""

from __future__ import annotations

from typing import Any

import pytest

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.mappers import MapperContext, get_mapper
from wcm_bricks_transpiler.mappers.raw import (
    _block_namespace_id,
    _namespace_css,
    _prefix_selectors,
    _split_selectors_top_level,
)
from wcm_types.enums import BlockType


def _resolver(asset_id: int) -> dict[str, Any]:
    return {"url": f"/uploads/asset-{asset_id}.webp"}


def _ctx() -> MapperContext:
    return MapperContext(
        project_id=1, page_id=1, page_lang="es",
        id_gen=IdGenerator(project_id=1, page_id=1),
        asset_resolver=_resolver,
    )


# =========================== AI_GENERATED ===========================


def test_ai_generated_empty_block_is_residual() -> None:
    mapper = get_mapper(BlockType.AI_GENERATED)
    res = mapper({"bricks_elements": []}, 0, BlockType.AI_GENERATED, "0", _ctx())
    assert res.elements == []
    assert res.residual is not None
    assert "vacío" in res.residual.title


def test_ai_generated_emit_elements_with_id_remap() -> None:
    """IDs antiguos se reasignan vía id_gen para evitar colisión con
    otros bloques de la misma página. La jerarquía interna se preserva."""
    elements = [
        {"id": "old_a", "name": "section", "parent": "0",
         "children": ["old_b"], "settings": {}},
        {"id": "old_b", "name": "container", "parent": "old_a",
         "children": ["old_c"], "settings": {}},
        {"id": "old_c", "name": "heading", "parent": "old_b",
         "children": [], "settings": {"text": "Hello"}},
    ]
    mapper = get_mapper(BlockType.AI_GENERATED)
    res = mapper(
        {"bricks_elements": elements, "notes": ""},
        0, BlockType.AI_GENERATED, "con001", _ctx(),
    )
    assert len(res.elements) == 3
    # IDs reasignados (no son los originales).
    new_ids = [e.id for e in res.elements]
    assert "old_a" not in new_ids
    assert "old_b" not in new_ids

    # El primer elemento (section) ahora tiene parent = "con001" (parent
    # del bloque), no "0" — porque el outer transpile_page wrapping ya
    # asigna el container.
    section = res.elements[0]
    assert section.parent == "con001"
    # Container tiene parent = section.id reasignado.
    container = res.elements[1]
    assert container.parent == section.id
    # Heading tiene parent = container.id.
    heading = res.elements[2]
    assert heading.parent == container.id


def test_ai_generated_parent_desconocido_anclado_a_block_parent() -> None:
    """Si Claude devuelve un parent que NO está en el array, se ancla
    al parent del bloque (defensive)."""
    elements = [
        {"id": "x1", "name": "block", "parent": "ghost", "children": [], "settings": {}},
    ]
    mapper = get_mapper(BlockType.AI_GENERATED)
    res = mapper(
        {"bricks_elements": elements},
        0, BlockType.AI_GENERATED, "con001", _ctx(),
    )
    assert len(res.elements) == 1
    assert res.elements[0].parent == "con001"


def test_ai_generated_skip_elementos_sin_id() -> None:
    """Elementos sin `id` o con id no-string → skipeados, residual emitida."""
    elements = [
        {"id": "good1", "name": "section", "parent": "0", "children": [], "settings": {}},
        {"name": "block", "parent": "0", "children": [], "settings": {}},  # sin id
    ]
    mapper = get_mapper(BlockType.AI_GENERATED)
    res = mapper(
        {"bricks_elements": elements},
        0, BlockType.AI_GENERATED, "0", _ctx(),
    )
    assert len(res.elements) == 1
    assert res.residual is not None
    assert "id inválido" in res.residual.description


# =========================== RAW_HTML ===========================


def test_raw_html_empty_block_is_residual() -> None:
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper({"html": "", "css": ""}, 0, BlockType.RAW_HTML, "0", _ctx())
    assert res.elements == []
    assert res.residual is not None
    assert "vacío" in res.residual.title


def test_raw_html_emite_un_elemento_code() -> None:
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper(
        {"html": "<div>hello</div>", "css": ".x { color: red; }"},
        0, BlockType.RAW_HTML, "con001", _ctx(),
    )
    assert len(res.elements) == 1
    el = res.elements[0]
    assert el.name == "code"
    assert el.parent == "con001"
    assert el.settings["executeCode"] is True
    # HTML wrapped en data-wcm-block + <style> al final.
    code = el.settings["code"]
    assert 'data-wcm-block="' in code
    assert "<div>hello</div>" in code
    assert "<style>" in code
    assert "color: red" in code


def test_raw_html_namespace_aisla_reglas() -> None:
    """Las reglas CSS deben prefijarse con [data-wcm-block]."""
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper(
        {"html": "<p>x</p>", "css": "p { color: blue; }"},
        0, BlockType.RAW_HTML, "0", _ctx(),
    )
    code = res.elements[0].settings["code"]
    # `[data-wcm-block="xxx"] p { ... }` debe aparecer.
    import re

    assert re.search(r'\[data-wcm-block="[a-z0-9]{6}"\] p', code), \
        f"Expected namespaced selector, got: {code[-200:]}"


def test_raw_html_sanitize_script() -> None:
    """<script> debe eliminarse del HTML antes de inyectar."""
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper(
        {
            "html": "<div>x</div><script>alert('xss')</script>",
            "css": "",
        },
        0, BlockType.RAW_HTML, "0", _ctx(),
    )
    code = res.elements[0].settings["code"]
    assert "<script" not in code.lower()
    assert "alert" not in code


def test_raw_html_sanitize_event_handlers() -> None:
    """onclick="..." debe eliminarse del HTML."""
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper(
        {"html": '<button onclick="evil()">x</button>', "css": ""},
        0, BlockType.RAW_HTML, "0", _ctx(),
    )
    code = res.elements[0].settings["code"]
    assert "onclick" not in code.lower()


def test_raw_html_sanitize_php() -> None:
    """`<?php ... ?>` debe eliminarse — Bricks executeCode no debe correr PHP."""
    mapper = get_mapper(BlockType.RAW_HTML)
    res = mapper(
        {"html": "<div>before<?php echo 'evil'; ?>after</div>", "css": ""},
        0, BlockType.RAW_HTML, "0", _ctx(),
    )
    code = res.elements[0].settings["code"]
    assert "<?php" not in code
    assert "echo 'evil'" not in code


# =========================== _namespace_css ===========================


def test_namespace_css_selector_simple() -> None:
    out, err = _namespace_css("h1 { color: red; }", "abc123")
    assert err is None
    assert '[data-wcm-block="abc123"] h1' in out
    assert "color: red" in out


def test_namespace_css_multiples_selectores_coma() -> None:
    """Los selectores separados por coma se prefijan individualmente."""
    out, err = _namespace_css("h1, h2 { color: red; }", "abc123")
    assert err is None
    assert '[data-wcm-block="abc123"] h1' in out
    assert '[data-wcm-block="abc123"] h2' in out


def test_namespace_css_no_rompe_is_paren() -> None:
    """`:is(a,b)` no debe partirse por la coma interna."""
    out, _ = _namespace_css("h1:is(.a, .b) { color: red; }", "abc123")
    # Debe quedar UN selector (no dos).
    assert out.count("h1:is(.a, .b)") == 1


def test_namespace_css_at_media_recursivo() -> None:
    """@media → las reglas internas se namespacean, pero el at-rule
    queda preservado."""
    css = "@media (max-width: 600px) { .card { padding: 1rem; } }"
    out, err = _namespace_css(css, "abc123")
    assert err is None
    assert "@media" in out
    assert '[data-wcm-block="abc123"] .card' in out


def test_namespace_css_font_face_se_preserva() -> None:
    """@font-face es global → no se namespacea."""
    css = '@font-face { font-family: "X"; src: url("x.woff2"); }'
    out, err = _namespace_css(css, "abc123")
    assert err is None
    assert "@font-face" in out
    # NO se prefija (no debe haber [data-wcm-block] dentro del @font-face).
    assert "[data-wcm-block" not in out


def test_namespace_css_keyframes_se_preserva() -> None:
    """@keyframes es global — animations referenciadas desde dentro del
    namespace siguen funcionando."""
    css = "@keyframes fade { 0% { opacity: 0 } 100% { opacity: 1 } }"
    out, err = _namespace_css(css, "abc123")
    assert err is None
    assert "@keyframes fade" in out


def test_namespace_css_import_se_elimina() -> None:
    """@import desaparece — Bricks code element no las carga limpio."""
    css = '@import url("foo.css"); h1 { color: red; }'
    out, err = _namespace_css(css, "abc123")
    assert err is None
    assert "@import" not in out
    # h1 sigue presente y namespaceado.
    assert '[data-wcm-block="abc123"] h1' in out


def test_namespace_css_body_root_reemplazados() -> None:
    """`:root`, `html`, `body` no tienen sentido dentro del namespace.
    Se reemplazan por el prefix sin selector adicional."""
    css = "body { background: black; } :root { --x: 1; }"
    out, err = _namespace_css(css, "abc123")
    assert err is None
    # El prefix queda sin selector adicional para body/root.
    assert '[data-wcm-block="abc123"] body' not in out
    assert '[data-wcm-block="abc123"] :root' not in out
    assert '[data-wcm-block="abc123"]{' in out or '[data-wcm-block="abc123"] {' in out


def test_namespace_css_vacio() -> None:
    out, err = _namespace_css("", "abc123")
    assert out == ""
    assert err is None


def test_namespace_css_re_namespace_no_duplica() -> None:
    """Si el CSS ya tiene `[data-wcm-block]`, no se anida un segundo prefix."""
    css = '[data-wcm-block="other"] .card { color: red; }'
    out, err = _namespace_css(css, "newone")
    assert err is None
    # No debe haber doble prefix.
    assert out.count('[data-wcm-block') == 1


# =========================== helpers ===========================


def test_split_selectors_top_level_basico() -> None:
    assert _split_selectors_top_level("h1, h2, h3") == ["h1", " h2", " h3"]


def test_split_selectors_top_level_no_parte_dentro_de_is() -> None:
    assert _split_selectors_top_level("h1:is(a,b), h2") == ["h1:is(a,b)", " h2"]


def test_split_selectors_top_level_no_parte_dentro_de_attr() -> None:
    assert _split_selectors_top_level('a[href*=","], b') == ['a[href*=","]', " b"]


def test_prefix_selectors_simple() -> None:
    out = _prefix_selectors("h1, h2", "abc123")
    assert out == '[data-wcm-block="abc123"] h1,[data-wcm-block="abc123"] h2'


def test_block_namespace_id_estable() -> None:
    a = _block_namespace_id(0, "<div>x</div>")
    b = _block_namespace_id(0, "<div>x</div>")
    assert a == b
    assert len(a) == 6
    assert a.isalnum()


def test_block_namespace_id_cambia_por_order_index() -> None:
    a = _block_namespace_id(0, "<div>x</div>")
    b = _block_namespace_id(1, "<div>x</div>")
    assert a != b


# ---------- registry ----------


def test_registry_devuelve_mappers_correctos() -> None:
    """Sanity: BlockType.AI_GENERATED y RAW_HTML están en REGISTRY."""
    from wcm_bricks_transpiler.mappers import REGISTRY, get_mapper
    from wcm_bricks_transpiler.mappers.ai import map_ai_generated
    from wcm_bricks_transpiler.mappers.raw import map_raw_html

    assert REGISTRY[BlockType.AI_GENERATED] is map_ai_generated
    assert REGISTRY[BlockType.RAW_HTML] is map_raw_html
    assert get_mapper(BlockType.AI_GENERATED) is map_ai_generated
    assert get_mapper(BlockType.RAW_HTML) is map_raw_html
