"""Tests del catálogo canónico de Bricks Global Classes (v0.28.0 B11)."""

from __future__ import annotations

from wcm_bricks_transpiler.global_classes_catalog import (
    CANONICAL_CLASS_IDS,
    build_canonical_catalog,
    list_canonical_ids,
)


def test_catalog_has_12_canonical_classes() -> None:
    classes = build_canonical_catalog(None)
    assert len(classes) == 12
    ids = [c["id"] for c in classes]
    assert set(ids) == set(CANONICAL_CLASS_IDS)


def test_catalog_with_none_theme_returns_defaults() -> None:
    """Sin theme, fallbacks razonables."""
    classes = build_canonical_catalog(None)
    h1 = next(c for c in classes if c["id"] == "wcm-h1")
    assert h1["settings"]["_typography"]["font-size"] == "2.5rem"
    assert h1["settings"]["_typography"]["font-weight"] == "700"


def test_catalog_uses_theme_typography_when_available() -> None:
    theme = {
        "typography": {
            "h1": {
                "font-family": "Playfair Display",
                "font-size": "3.5rem",
                "font-weight": "800",
            },
            "body": {"font-family": "Inter", "font-size": "1.125rem"},
        }
    }
    classes = build_canonical_catalog(theme)
    h1 = next(c for c in classes if c["id"] == "wcm-h1")
    assert h1["settings"]["_typography"]["font-family"] == "Playfair Display"
    assert h1["settings"]["_typography"]["font-size"] == "3.5rem"
    assert h1["settings"]["_typography"]["font-weight"] == "800"
    body = next(c for c in classes if c["id"] == "wcm-body")
    assert body["settings"]["_typography"]["font-family"] == "Inter"
    assert body["settings"]["_typography"]["font-size"] == "1.125rem"


def test_h3_h4_derive_from_h2_size() -> None:
    """h3=0.8·h2, h4=0.65·h2."""
    theme = {"typography": {"h2": {"font-size": "2rem"}}}
    classes = build_canonical_catalog(theme)
    h3 = next(c for c in classes if c["id"] == "wcm-h3")
    h4 = next(c for c in classes if c["id"] == "wcm-h4")
    assert h3["settings"]["_typography"]["font-size"] == "1.6rem"
    assert h4["settings"]["_typography"]["font-size"] == "1.3rem"


def test_body_large_small_scale_correctly() -> None:
    theme = {"typography": {"body": {"font-size": "1rem"}}}
    classes = build_canonical_catalog(theme)
    body_lg = next(c for c in classes if c["id"] == "wcm-body-large")
    body_sm = next(c for c in classes if c["id"] == "wcm-body-small")
    assert body_lg["settings"]["_typography"]["font-size"] == "1.25rem"
    # 0.875 → "0.875rem" (truncado 3 cifras significativas)
    assert body_sm["settings"]["_typography"]["font-size"].startswith("0.875")


def test_buttons_use_var_color_refs() -> None:
    classes = build_canonical_catalog(None)
    btn_pri = next(c for c in classes if c["id"] == "wcm-btn-primary")
    btn_sec = next(c for c in classes if c["id"] == "wcm-btn-secondary")
    btn_out = next(c for c in classes if c["id"] == "wcm-btn-outline")
    assert btn_pri["settings"]["_background"]["color"] == {"raw": "var(--bricks-color-primary)"}
    assert btn_sec["settings"]["_background"]["color"] == {"raw": "var(--bricks-color-secondary)"}
    # Outline: sin _background, sí _border con primary
    assert "_background" not in btn_out["settings"]
    assert btn_out["settings"]["_border"]["color"] == {"raw": "var(--bricks-color-primary)"}


def test_section_paddings_use_theme_spacing_when_available() -> None:
    theme = {"spacing": {"section_y": "8rem"}}
    classes = build_canonical_catalog(theme)
    pad_lg = next(c for c in classes if c["id"] == "wcm-section-padding-lg")
    pad_md = next(c for c in classes if c["id"] == "wcm-section-padding-md")
    assert pad_md["settings"]["_padding"]["top"] == "8rem"
    # lg = 1.5x section_y = 12rem
    assert pad_lg["settings"]["_padding"]["top"] == "12rem"


def test_typography_keys_are_kebab_case() -> None:
    """Validación crítica: NUNCA snake_case ni camelCase."""
    classes = build_canonical_catalog(None)
    for c in classes:
        typo = c["settings"].get("_typography", {})
        for k in typo:
            if k == "color":
                continue
            assert "-" in k or k.isalpha(), f"Key inválida en {c['id']}: {k}"
            assert "_" not in k, f"Underscore en {c['id']}._typography.{k}"


def test_list_canonical_ids_returns_all_ids() -> None:
    ids = list_canonical_ids()
    assert "wcm-h1" in ids
    assert "wcm-btn-primary" in ids
    assert len(ids) == 12


def test_make_class_has_id_name_settings_shape() -> None:
    """Cada entrada tiene la triple (id, name, settings) que wp_deployer espera."""
    classes = build_canonical_catalog(None)
    for c in classes:
        assert set(c.keys()) == {"id", "name", "settings"}
        assert c["id"] == c["name"]
        assert isinstance(c["settings"], dict)
