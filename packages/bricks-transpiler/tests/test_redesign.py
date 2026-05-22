"""Tests del paquete redesign (Sprint v0.25.0 B5).

SectionPicker + SlotMapper. Sin BD, sin SQLAlchemy — son módulos puros.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wcm_bricks_transpiler.redesign import (
    SectionPicker,
    SlotMapper,
    SlotMapperError,
    load_sections_index,
)
from wcm_bricks_transpiler.redesign.section_picker import _stable_hash

# Path al mock catalog (relativo al root del repo).
MOCK_CATALOG = Path(__file__).resolve().parents[3] / "docs" / "templates" / "brickstemplate-mock"


# ---------- SectionPicker ----------


def test_load_sections_index_devuelve_lista_vacia_si_no_existe(tmp_path: Path) -> None:
    """Catálogo inexistente → lista vacía, no crashea."""
    out = load_sections_index(tmp_path / "nonexistent")
    assert out == []


def test_load_sections_index_mock_catalog_4_templates() -> None:
    """Mock catalog tiene 4 templates."""
    templates = load_sections_index(MOCK_CATALOG)
    assert len(templates) == 4
    categories = {t["category"] for t in templates}
    assert categories == {"hero", "features", "cta"}


def test_section_picker_match_full_filters() -> None:
    """Hero + agency + formal → matchea hero-minimalist-001."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="hero",
        business_name="Acme Consulting",
        business_sector="agency",
        business_tone="formal",
    )
    assert picked is not None
    assert picked.template_id == "hero-minimalist-001"
    assert picked.fallback_level == 0
    assert picked.template_json["_meta"]["id"] == "hero-minimalist-001"


def test_section_picker_match_relax_tone() -> None:
    """Hero + agency + tone "weird" no matchea por tone → relax → matchea por sector."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="hero",
        business_name="Acme",
        business_sector="agency",
        business_tone="weird_tone_no_existe",
    )
    assert picked is not None
    assert picked.fallback_level == 1  # relaxed tone
    assert picked.template_id == "hero-minimalist-001"  # solo este matchea agency


def test_section_picker_match_relax_sector() -> None:
    """Hero + sector "weird" → relax sector → cualquier hero."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="hero",
        business_name="Acme",
        business_sector="weird_sector_no_existe",
        business_tone="weird_tone_no_existe",
    )
    assert picked is not None
    assert picked.fallback_level == 2  # relaxed sector y tone
    # Cualquiera de los dos heroes.
    assert picked.template_id in ("hero-minimalist-001", "hero-playful-001")


def test_section_picker_no_match_para_categoria_inexistente() -> None:
    """Pricing no existe en mock catalog → None."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="pricing",
        business_name="Acme",
        business_sector="agency",
        business_tone="formal",
    )
    assert picked is None


def test_section_picker_eleccion_determinista() -> None:
    """Mismo business_name + mismos filtros → mismo template entre runs."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    p1 = picker.pick(
        section_type="hero", business_name="Acme",
        business_sector="weird", business_tone="weird",  # fuerza relax sector
    )
    p2 = picker.pick(
        section_type="hero", business_name="Acme",
        business_sector="weird", business_tone="weird",
    )
    assert p1 is not None
    assert p2 is not None
    assert p1.template_id == p2.template_id


def test_section_picker_business_name_distinto_puede_dar_template_distinto() -> None:
    """Cuando hay 2+ candidatos, hash(business.name) puede variar la elección."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    # Forzamos relax para tener 2 candidatos hero.
    p1 = picker.pick(
        section_type="hero", business_name="Acme",
        business_sector="weird", business_tone="weird",
    )
    p2 = picker.pick(
        section_type="hero", business_name="ZetaXXXY",
        business_sector="weird", business_tone="weird",
    )
    # No garantizamos que sean diferentes (mismo idx puede caer), pero
    # comprobamos que `_stable_hash` da distinto.
    assert _stable_hash("Acme") != _stable_hash("ZetaXXXY")
    assert p1 is not None and p2 is not None


def test_section_picker_cta_sin_fits_sectors_acepta_cualquier_sector() -> None:
    """cta-generic-001 tiene fits_sectors=[] → matchea cualquier sector."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="cta",
        business_name="Acme",
        business_sector="agency",
        business_tone="formal",
    )
    assert picked is not None
    assert picked.template_id == "cta-generic-001"


# ---------- SlotMapper ----------


def test_slot_mapper_aplica_slot_simple() -> None:
    """`content[1].settings.text` → `section.headline`."""
    template = {
        "content": [
            {"id": "secaaa", "name": "section", "parent": "0", "children": ["headaa"], "settings": {}},
            {"id": "headaa", "name": "heading", "parent": "secaaa", "children": [], "settings": {"text": "PLACEHOLDER"}},
        ]
    }
    section = {"type": "hero", "headline": "Mi nuevo titulo"}
    slot_map = {"content[1].settings.text": "headline"}

    mapper = SlotMapper()
    result = mapper.apply(template=template, section=section, slot_map=slot_map)

    assert result["content"][1]["settings"]["text"] == "Mi nuevo titulo"
    # IDs regenerados.
    assert result["content"][0]["id"] != "secaaa"
    assert result["content"][1]["id"] != "headaa"


def test_slot_mapper_aplica_slot_nested_dot_notation() -> None:
    """`content[0].settings.link.url` ← `section.cta.url`."""
    template = {
        "content": [
            {"id": "btnxxx", "name": "button", "parent": "0", "children": [],
             "settings": {"link": {"url": "#"}, "text": "X"}},
        ]
    }
    section = {"type": "cta", "cta": {"text": "Empezar", "url": "https://x.com"}}
    slot_map = {
        "content[0].settings.text": "cta.text",
        "content[0].settings.link.url": "cta.url",
    }

    mapper = SlotMapper()
    result = mapper.apply(template=template, section=section, slot_map=slot_map)

    assert result["content"][0]["settings"]["text"] == "Empezar"
    assert result["content"][0]["settings"]["link"]["url"] == "https://x.com"


def test_slot_mapper_ignora_brief_key_inexistente() -> None:
    """Si la key del brief no existe, el slot NO se toca (log warning)."""
    template = {
        "content": [
            {"id": "headaa", "name": "heading", "parent": "0", "children": [],
             "settings": {"text": "ORIGINAL"}},
        ]
    }
    section = {"type": "hero"}  # sin headline
    slot_map = {"content[0].settings.text": "headline"}

    mapper = SlotMapper()
    result = mapper.apply(template=template, section=section, slot_map=slot_map)

    assert result["content"][0]["settings"]["text"] == "ORIGINAL"


def test_slot_mapper_ids_regenerados_y_referencias_actualizadas() -> None:
    """Los IDs cambian + parent/children referencian los nuevos IDs."""
    template = {
        "content": [
            {"id": "secxxx", "name": "section", "parent": "0", "children": ["headyy"], "settings": {}},
            {"id": "headyy", "name": "heading", "parent": "secxxx", "children": [], "settings": {"text": "x"}},
        ]
    }
    mapper = SlotMapper()
    result = mapper.apply(template=template, section={}, slot_map={})

    new_sec_id = result["content"][0]["id"]
    new_head_id = result["content"][1]["id"]
    assert new_sec_id != "secxxx"
    assert new_head_id != "headyy"
    assert result["content"][1]["parent"] == new_sec_id  # ref actualizada
    assert result["content"][0]["children"] == [new_head_id]
    # parent "0" se preserva (top-level).
    assert result["content"][0]["parent"] == "0"


def test_slot_mapper_asset_resolver_se_invoca_para_image_slot() -> None:
    """`.image.url` con asset_resolver inyectado → resuelve URL real."""
    template = {
        "content": [
            {"id": "imgaaa", "name": "image", "parent": "0", "children": [],
             "settings": {"image": {"url": "PLACEHOLDER_URL", "id": None}}},
        ]
    }
    section = {"type": "hero", "image_id": 42}
    slot_map = {
        "content[0].settings.image.url": "image_id",
        "content[0].settings.image.id": "image_id",
    }

    def resolver(asset_id):
        assert asset_id == 42
        return {
            "url": "https://wp/uploads/2026/05/imagen.webp",
            "wp_attachment_id": 999,
            "alt_text": "Mi imagen",
        }

    mapper = SlotMapper(asset_resolver=resolver)
    result = mapper.apply(template=template, section=section, slot_map=slot_map)

    assert result["content"][0]["settings"]["image"]["url"] == "https://wp/uploads/2026/05/imagen.webp"
    assert result["content"][0]["settings"]["image"]["id"] == 999


def test_slot_mapper_path_inexistente_no_rompe() -> None:
    """Path que no existe en el template → warning + skip (no excepción)."""
    template = {
        "content": [
            {"id": "headaa", "name": "heading", "parent": "0", "children": [], "settings": {"text": "x"}},
        ]
    }
    slot_map = {"content[5].settings.nonexistent.deep": "headline"}
    mapper = SlotMapper()
    # No debería lanzar (el _set_path raise → atrapado y logged).
    result = mapper.apply(template=template, section={"headline": "X"}, slot_map=slot_map)
    assert result["content"][0]["settings"]["text"] == "x"


def test_slot_mapper_template_shape_invalida_levanta_error() -> None:
    """Template sin `content` ni `name+settings` → SlotMapperError."""
    mapper = SlotMapper()
    with pytest.raises(SlotMapperError):
        mapper.apply(template={"foo": "bar"}, section={}, slot_map={})


def test_slot_mapper_acepta_elemento_individual_como_template() -> None:
    """Template como dict con `name+settings` se normaliza a `{content: [el]}`."""
    template = {"id": "headaa", "name": "heading", "parent": "0", "children": [], "settings": {"text": "X"}}
    mapper = SlotMapper()
    result = mapper.apply(template=template, section={}, slot_map={})
    assert isinstance(result["content"], list)
    assert len(result["content"]) == 1


def test_slot_mapper_deep_copy_no_muta_template_original() -> None:
    """El template original NO se modifica entre apply() calls (deep copy)."""
    template = {
        "content": [
            {"id": "headaa", "name": "heading", "parent": "0", "children": [], "settings": {"text": "ORIGINAL"}},
        ]
    }
    original_id = template["content"][0]["id"]
    original_text = template["content"][0]["settings"]["text"]

    mapper = SlotMapper()
    mapper.apply(
        template=template, section={"headline": "X"},
        slot_map={"content[0].settings.text": "headline"},
    )
    # Original intacto.
    assert template["content"][0]["id"] == original_id
    assert template["content"][0]["settings"]["text"] == original_text


# ---------- E2E: SectionPicker + SlotMapper aplicados a mock catalog ----------


def test_e2e_pick_hero_minimalist_y_aplicar_brief() -> None:
    """Caso real: hero del catálogo + Brief.section → JSON Bricks completo."""
    picker = SectionPicker(catalog_dir=MOCK_CATALOG)
    picked = picker.pick(
        section_type="hero",
        business_name="Mariya Design",
        business_sector="agency",
        business_tone="formal",
    )
    assert picked is not None

    section = {
        "type": "hero",
        "headline": "Diseño de marca con alma",
        "subheadline": "Identidades visuales para empresas que quieren destacar.",
        "cta": {"text": "Hablemos", "url": "/contacto"},
    }
    mapper = SlotMapper()
    result = mapper.apply(
        template=picked.template_json,
        section=section,
        slot_map=picked.slot_map,
    )

    # Verificaciones: el headline + subheadline + cta se aplicaron.
    serialized = json.dumps(result, ensure_ascii=False)
    assert "Diseño de marca con alma" in serialized
    assert "Identidades visuales" in serialized
    assert "Hablemos" in serialized
    assert "/contacto" in serialized
    # PLACEHOLDER originales NO están.
    assert "TEMPLATE PLACEHOLDER" not in serialized
