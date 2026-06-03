"""Tests de la taxonomía semántica canónica (v0.29.0 B1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wcm_bricks_transpiler.redesign.semantic_taxonomy import (
    CANONICAL_SECTION_TYPES,
    EXTRACTOR_NOISE_TYPES,
    NON_SECTION_CATEGORIES,
    SECTION_DESCRIPTIONS,
    canonical_for_extractor_type,
    is_canonical_type,
)


def test_all_canonical_types_have_description() -> None:
    """Cada tipo canónico debe tener una descripción para el LLM."""
    for t in CANONICAL_SECTION_TYPES:
        assert t in SECTION_DESCRIPTIONS, f"Falta descripción para {t!r}"
        assert len(SECTION_DESCRIPTIONS[t]) > 40, (
            f"Descripción demasiado corta para {t!r}"
        )


def test_canonical_and_non_section_are_disjoint() -> None:
    """Un tipo no puede ser canónico Y non-section a la vez."""
    overlap = set(CANONICAL_SECTION_TYPES) & NON_SECTION_CATEGORIES
    assert not overlap, f"Solapamiento canonical/non-section: {overlap}"


def test_canonical_types_no_duplicates() -> None:
    assert len(CANONICAL_SECTION_TYPES) == len(set(CANONICAL_SECTION_TYPES))


def _load_catalog_categories() -> set[str] | None:
    """Devuelve el set de categorías presentes en sections-index.json o
    None si el catálogo no está descargado (CI nuevo / dev fresh)."""
    repo_root = Path(__file__).resolve().parents[3]
    index_path = repo_root / "docs/templates/brickstemplate/sections-index.json"
    if not index_path.exists():
        return None
    data = json.loads(index_path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("templates", [])
    return {e.get("category") for e in items if e.get("category")}


def test_canonical_types_all_exist_in_brickstemplate_catalog() -> None:
    """Cada CANONICAL_SECTION_TYPES debe tener ≥1 template en el catálogo."""
    cats = _load_catalog_categories()
    if cats is None:
        pytest.skip("Catálogo brickstemplate no descargado en este entorno")
    missing = set(CANONICAL_SECTION_TYPES) - cats
    assert not missing, (
        f"Tipos canónicos sin templates en catálogo brickstemplate: {missing}"
    )


def test_catalog_categories_covered_by_taxonomy() -> None:
    """Toda categoría del catálogo debe estar clasificada (canónica O
    non-section) — si aparece una nueva al actualizar el catálogo, falla
    el test y obliga al desarrollador a decidir dónde va."""
    cats = _load_catalog_categories()
    if cats is None:
        pytest.skip("Catálogo brickstemplate no descargado en este entorno")
    known = set(CANONICAL_SECTION_TYPES) | NON_SECTION_CATEGORIES
    unclassified = cats - known
    assert not unclassified, (
        f"Categorías del catálogo sin clasificar en taxonomía: "
        f"{unclassified}. Añádelas a CANONICAL_SECTION_TYPES o "
        f"NON_SECTION_CATEGORIES."
    )


def test_canonical_for_extractor_type_direct_mappings() -> None:
    assert canonical_for_extractor_type("hero") == "hero"
    assert canonical_for_extractor_type("cta") == "cta"
    assert canonical_for_extractor_type("pricing") == "pricing"
    assert canonical_for_extractor_type("faq") == "faqs"
    assert canonical_for_extractor_type("form") == "contact_form"
    assert canonical_for_extractor_type("testimonial") == "testimonials"
    assert canonical_for_extractor_type("slider") == "slider"


def test_canonical_for_extractor_type_ambiguous_returns_none() -> None:
    """Los block types ambiguos requieren LLM — fast-path debe devolver None."""
    for ambiguous in ("text", "heading", "image", "grid", "gallery", "accordion", "tabs"):
        assert canonical_for_extractor_type(ambiguous) is None


def test_canonical_for_extractor_type_unknown_returns_none() -> None:
    assert canonical_for_extractor_type("xxxxxxxxx") is None
    assert canonical_for_extractor_type("") is None


def test_canonical_for_extractor_type_always_returns_canonical_or_none() -> None:
    """Postcondición: el fast-path nunca devuelve un tipo no-canónico."""
    for et in ("hero", "cta", "pricing", "faq", "form", "testimonial",
               "slider", "gallery", "text", "heading", "image", "grid",
               "accordion", "tabs", "unknown"):
        out = canonical_for_extractor_type(et)
        assert out is None or is_canonical_type(out), (
            f"Fast-path emitió tipo no-canónico para {et!r}: {out!r}"
        )


def test_is_canonical_type() -> None:
    assert is_canonical_type("hero")
    assert is_canonical_type("features")
    assert is_canonical_type("footer")
    assert not is_canonical_type("text")
    assert not is_canonical_type("header")  # header es non-section
    assert not is_canonical_type("")
    assert not is_canonical_type("nonexistent_xxx")


def test_extractor_noise_types_disjoint_from_canonical_fastpath() -> None:
    """Tipos ruido del extractor no deben tener un mapping directo."""
    for noise in EXTRACTOR_NOISE_TYPES:
        assert canonical_for_extractor_type(noise) is None
