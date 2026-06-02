"""Tests del script scripts/import_brickstemplate_clipboard.py (v0.28.0 B12)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).parents[2] / "scripts" / "import_brickstemplate_clipboard.py"
    spec = importlib.util.spec_from_file_location("import_bt_clip", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE_PAYLOAD = {
    "content": [
        {
            "id": "uqnjfz", "name": "section", "parent": 0,
            "children": ["oiyzux"],
            "settings": {"_cssGlobalClasses": ["gboscc"]},
            "label": "Footer 2",
        },
        {
            "id": "oiyzux", "name": "container", "parent": "uqnjfz",
            "children": [],
            "settings": {},
        },
    ],
    "source": "bricksCopiedElements",
    "sourceUrl": "https://wireframe.brickstemplate.com",
    "version": "2.0.2",
    "globalClasses": [
        {"id": "gboscc", "name": "footer-2-migrator", "settings": {}},
    ],
    "globalElements": [],
}


# -----------------------------------------------------------------------------
# parse_bricks_payload
# -----------------------------------------------------------------------------


def test_parse_bricks_payload_valid() -> None:
    mod = _load_script_module()
    text = json.dumps(SAMPLE_PAYLOAD)
    result = mod.parse_bricks_payload(text)
    assert result is not None
    assert result["source"] == "bricksCopiedElements"
    assert len(result["content"]) == 2


def test_parse_bricks_payload_rejects_random_text() -> None:
    mod = _load_script_module()
    assert mod.parse_bricks_payload("https://example.com") is None
    assert mod.parse_bricks_payload("hello world") is None
    assert mod.parse_bricks_payload("") is None


def test_parse_bricks_payload_rejects_other_json() -> None:
    mod = _load_script_module()
    assert mod.parse_bricks_payload('{"foo": "bar"}') is None
    assert mod.parse_bricks_payload('[1, 2, 3]') is None


def test_parse_bricks_payload_rejects_wrong_source() -> None:
    mod = _load_script_module()
    payload = {**SAMPLE_PAYLOAD, "source": "otherTool"}
    assert mod.parse_bricks_payload(json.dumps(payload)) is None


def test_parse_bricks_payload_rejects_content_not_list() -> None:
    mod = _load_script_module()
    payload = {**SAMPLE_PAYLOAD, "content": "not-a-list"}
    assert mod.parse_bricks_payload(json.dumps(payload)) is None


# -----------------------------------------------------------------------------
# slugify
# -----------------------------------------------------------------------------


def test_slugify_basic() -> None:
    mod = _load_script_module()
    assert mod.slugify("Footer 2") == "footer-2"
    assert mod.slugify("Hero — Premium") == "hero-premium"
    assert mod.slugify("Call To Action 1.0") == "call-to-action-1-0"
    assert mod.slugify("") == "untitled"


# -----------------------------------------------------------------------------
# content_digest — dedup
# -----------------------------------------------------------------------------


def test_content_digest_stable_for_same_content() -> None:
    mod = _load_script_module()
    d1 = mod.content_digest(SAMPLE_PAYLOAD["content"])
    d2 = mod.content_digest(SAMPLE_PAYLOAD["content"])
    assert d1 == d2 and len(d1) == 16


def test_content_digest_differs_for_different_content() -> None:
    mod = _load_script_module()
    d1 = mod.content_digest(SAMPLE_PAYLOAD["content"])
    modified = [{**SAMPLE_PAYLOAD["content"][0], "id": "different"}]
    d2 = mod.content_digest(modified)
    assert d1 != d2


# -----------------------------------------------------------------------------
# build_index_entry
# -----------------------------------------------------------------------------


def test_build_index_entry_extracts_metadata() -> None:
    mod = _load_script_module()
    entry = mod.build_index_entry(
        "footer", "footer-2", "Footer 2", SAMPLE_PAYLOAD, "abc123",
    )
    assert entry["slug"] == "footer-2"
    assert entry["category"] == "footer"
    assert entry["file"] == "footer/footer-2.json"
    assert entry["n_elements"] == 2
    assert entry["n_global_classes"] == 1
    assert entry["source_url"] == "https://wireframe.brickstemplate.com"
    assert entry["bricks_version"] == "2.0.2"


def test_build_index_entry_detects_cta_and_image() -> None:
    mod = _load_script_module()
    payload_with_btn_img = {
        **SAMPLE_PAYLOAD,
        "content": [
            {"id": "x", "name": "section", "parent": 0, "settings": {}, "children": ["a", "b"]},
            {"id": "a", "name": "image", "parent": "x", "settings": {}, "children": []},
            {"id": "b", "name": "button", "parent": "x", "settings": {}, "children": []},
        ],
    }
    entry = mod.build_index_entry(
        "hero", "hero-1", "Hero 1", payload_with_btn_img, "abc",
    )
    assert entry["has_image"] is True
    assert entry["has_cta"] is True


def test_build_index_entry_no_cta_when_no_button() -> None:
    mod = _load_script_module()
    entry = mod.build_index_entry(
        "footer", "footer-2", "Footer 2", SAMPLE_PAYLOAD, "abc",
    )
    assert entry["has_cta"] is False


# -----------------------------------------------------------------------------
# detect_snake_case_settings — defensivo
# -----------------------------------------------------------------------------


def test_detect_snake_case_settings_finds_anti_pattern() -> None:
    mod = _load_script_module()
    content = [
        {"id": "x", "name": "heading", "settings": {
            "_typography": {"font_size": "2rem", "color": {"hex": "#000"}},
        }},
    ]
    bad = mod.detect_snake_case_settings(content)
    assert "heading.font_size" in bad


def test_detect_snake_case_settings_clean_when_kebab() -> None:
    mod = _load_script_module()
    content = [
        {"id": "x", "name": "heading", "settings": {
            "_typography": {"font-size": "2rem", "color": {"hex": "#000"}},
        }},
    ]
    assert mod.detect_snake_case_settings(content) == []


# -----------------------------------------------------------------------------
# find_unique_slug
# -----------------------------------------------------------------------------


def test_find_unique_slug_no_collision(tmp_path: Path) -> None:
    mod = _load_script_module()
    slug = mod.find_unique_slug(tmp_path, "footer-1")
    assert slug == "footer-1"


def test_find_unique_slug_with_collision(tmp_path: Path) -> None:
    mod = _load_script_module()
    (tmp_path / "footer-1.json").write_text("{}")
    (tmp_path / "footer-1-2.json").write_text("{}")
    slug = mod.find_unique_slug(tmp_path, "footer-1")
    assert slug == "footer-1-3"


# -----------------------------------------------------------------------------
# save_template — integration con tmp_path
# -----------------------------------------------------------------------------


def test_save_template_persists_and_indexes(tmp_path: Path, monkeypatch) -> None:
    mod = _load_script_module()
    monkeypatch.setattr(mod, "CATALOG_ROOT", tmp_path / "catalog")
    monkeypatch.setattr(mod, "INDEX_PATH", tmp_path / "catalog" / "sections-index.json")
    index: list = []
    slug, status, was_dup = mod.save_template("footer", SAMPLE_PAYLOAD, index)
    assert slug == "footer-2"
    assert status == "saved"
    assert was_dup is False
    assert (tmp_path / "catalog" / "footer" / "footer-2.json").exists()
    assert len(index) == 1
    assert index[0]["slug"] == "footer-2"


def test_save_template_detects_duplicate(tmp_path: Path, monkeypatch) -> None:
    mod = _load_script_module()
    monkeypatch.setattr(mod, "CATALOG_ROOT", tmp_path / "catalog")
    monkeypatch.setattr(mod, "INDEX_PATH", tmp_path / "catalog" / "sections-index.json")
    index: list = []
    mod.save_template("footer", SAMPLE_PAYLOAD, index)
    _, status, was_dup = mod.save_template("footer", SAMPLE_PAYLOAD, index)
    assert status == "duplicate"
    assert was_dup is True
    assert len(index) == 1  # no duplica


def test_save_template_handles_label_collision(tmp_path: Path, monkeypatch) -> None:
    """Dos templates con mismo `label` pero content distinto → sufijo -2."""
    mod = _load_script_module()
    monkeypatch.setattr(mod, "CATALOG_ROOT", tmp_path / "catalog")
    monkeypatch.setattr(mod, "INDEX_PATH", tmp_path / "catalog" / "sections-index.json")
    index: list = []
    mod.save_template("footer", SAMPLE_PAYLOAD, index)
    # Modificar para que tenga digest distinto pero mismo label
    p2 = {**SAMPLE_PAYLOAD, "content": [
        {**SAMPLE_PAYLOAD["content"][0], "id": "different_id"},
    ]}
    slug, status, _ = mod.save_template("footer", p2, index)
    assert slug == "footer-2-2"
    assert status == "saved"
    assert len(index) == 2
