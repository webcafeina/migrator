"""Tests del script scripts/enrich_brickstemplate_index.py (v0.28.0 B13)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).parents[2] / "scripts" / "enrich_brickstemplate_index.py"
    spec = importlib.util.spec_from_file_location("enrich_bt", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -----------------------------------------------------------------------------
# normalize_category
# -----------------------------------------------------------------------------


def test_normalize_category_known_aliases() -> None:
    mod = _load_script_module()
    assert mod.normalize_category("call-to-action") == "cta"
    assert mod.normalize_category("contact-us") == "contact_form"
    assert mod.normalize_category("pros-and-cons") == "pros_cons"
    assert mod.normalize_category("post-grid") == "post_grid"


def test_normalize_category_unknown_preserves() -> None:
    mod = _load_script_module()
    assert mod.normalize_category("hero") == "hero"
    assert mod.normalize_category("features") == "features"
    assert mod.normalize_category("foo-bar") == "foo-bar"


# -----------------------------------------------------------------------------
# generate_slot_map — heurística
# -----------------------------------------------------------------------------


def test_slot_map_heading_to_headline() -> None:
    mod = _load_script_module()
    content = [
        {"id": "sec", "name": "section", "settings": {}},
        {"id": "h1", "name": "heading", "settings": {"text": "Hi", "tag": "h1"}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm == {"content[1].settings.text": "headline"}


def test_slot_map_two_headings_assign_subheadline() -> None:
    mod = _load_script_module()
    content = [
        {"id": "h1", "name": "heading", "settings": {"text": "Main"}},
        {"id": "h2", "name": "heading", "settings": {"text": "Sub"}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[0].settings.text"] == "headline"
    assert sm["content[1].settings.text"] == "subheadline"


def test_slot_map_button_with_link() -> None:
    mod = _load_script_module()
    content = [
        {"id": "h1", "name": "heading", "settings": {"text": "Hi"}},
        {"id": "b1", "name": "button", "settings": {"text": "Buy", "link": {"url": "#"}}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[1].settings.text"] == "cta.text"
    assert sm["content[1].settings.link.url"] == "cta.url"


def test_slot_map_button_without_link_skips_link_slot() -> None:
    """Si el template no trae link, no inventamos el path."""
    mod = _load_script_module()
    content = [
        {"id": "b1", "name": "button", "settings": {"text": "Buy"}},  # sin link
    ]
    sm = mod.generate_slot_map(content)
    assert sm == {"content[0].settings.text": "cta.text"}


def test_slot_map_two_buttons_emit_secondary() -> None:
    mod = _load_script_module()
    content = [
        {"id": "b1", "name": "button", "settings": {"text": "Primary", "link": {"url": "#"}}},
        {"id": "b2", "name": "button", "settings": {"text": "Secondary", "link": {"url": "#"}}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[0].settings.text"] == "cta.text"
    assert sm["content[1].settings.text"] == "cta_secondary.text"
    assert sm["content[1].settings.link.url"] == "cta_secondary.url"


def test_slot_map_image_with_id_and_url() -> None:
    mod = _load_script_module()
    content = [
        {"id": "img", "name": "image", "settings": {
            "image": {"id": 42, "url": "https://x.jpg"}
        }},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[0].settings.image.url"] == "image_url"
    assert sm["content[0].settings.image.id"] == "image_id"


def test_slot_map_background_image() -> None:
    mod = _load_script_module()
    content = [
        {"id": "sec", "name": "section", "settings": {
            "_background": {"image": {"url": "https://bg.jpg"}}
        }},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[0].settings._background.image.url"] == "background_image_url"


def test_slot_map_text_basic_long_to_description() -> None:
    mod = _load_script_module()
    content = [
        {"id": "h1", "name": "heading", "settings": {"text": "Title"}},
        {"id": "t1", "name": "text-basic", "settings": {
            "text": "A long enough description that should be mapped as description content"
        }},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[1].settings.text"] == "description"


def test_slot_map_text_basic_short_skipped() -> None:
    """Texto corto (<40 chars) no se mapea — probablemente label decorativo."""
    mod = _load_script_module()
    content = [
        {"id": "t1", "name": "text-basic", "settings": {"text": "Short"}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm == {}


def test_slot_map_logo_element() -> None:
    mod = _load_script_module()
    content = [
        {"id": "lg", "name": "logo", "settings": {"logoText": "Acme Co"}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm["content[0].settings.logoText"] == "logo_text"


def test_slot_map_empty_content() -> None:
    mod = _load_script_module()
    assert mod.generate_slot_map([]) == {}


def test_slot_map_atomic_only_skipped() -> None:
    """Container/spacer/divider sueltos no generan slots."""
    mod = _load_script_module()
    content = [
        {"id": "c1", "name": "container", "settings": {}},
        {"id": "d1", "name": "divider", "settings": {}},
    ]
    sm = mod.generate_slot_map(content)
    assert sm == {}


# -----------------------------------------------------------------------------
# enrich_entry — integration con tmp_path
# -----------------------------------------------------------------------------


def test_enrich_entry_preserves_existing_slot_map(tmp_path: Path) -> None:
    """Si entrada ya tiene slot_map no vacío, se respeta override manual."""
    mod = _load_script_module()
    # Crear template real en disco
    template_dir = tmp_path / "hero"
    template_dir.mkdir()
    (template_dir / "hero-1.json").write_text(
        '{"content": [{"id": "x", "name": "heading", "settings": {"text": "X"}}]}'
    )
    entry = {
        "slug": "hero-1",
        "category": "hero",
        "file": "hero/hero-1.json",
        "slot_map": {"content[0].settings.text": "custom_field"},  # override
    }
    enriched = mod.enrich_entry(entry, tmp_path)
    # No se sobrescribe
    assert enriched["slot_map"] == {"content[0].settings.text": "custom_field"}


def test_enrich_entry_generates_slot_map_when_missing(tmp_path: Path) -> None:
    mod = _load_script_module()
    template_dir = tmp_path / "hero"
    template_dir.mkdir()
    (template_dir / "hero-1.json").write_text(
        '{"content": [{"id": "x", "name": "heading", "settings": {"text": "X"}}]}'
    )
    entry = {"slug": "hero-1", "category": "hero", "file": "hero/hero-1.json"}
    enriched = mod.enrich_entry(entry, tmp_path)
    assert enriched["slot_map"] == {"content[0].settings.text": "headline"}
    assert enriched["category_original"] == "hero"
    assert enriched["category"] == "hero"  # sin alias
    assert enriched["id"] == "hero-1"


def test_enrich_entry_normalizes_category(tmp_path: Path) -> None:
    mod = _load_script_module()
    template_dir = tmp_path / "call-to-action"
    template_dir.mkdir()
    (template_dir / "cta-1.json").write_text('{"content": []}')
    entry = {"slug": "cta-1", "category": "call-to-action", "file": "call-to-action/cta-1.json"}
    enriched = mod.enrich_entry(entry, tmp_path)
    assert enriched["category"] == "cta"
    assert enriched["category_original"] == "call-to-action"
