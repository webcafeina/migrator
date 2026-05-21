"""Tests end-to-end de transpile_page: ContentBlocks → JSON Bricks válido."""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler import (
    TranspileContext,
    transpile_page,
    validate_bricks_page,
)
from wcm_types.enums import BlockType


def _resolver(asset_id: int) -> dict[str, Any]:
    return {
        "url": f"/wp-content/uploads/asset-{asset_id}.webp",
        "wp_attachment_id": 1000 + asset_id,
        "width": 1200,
        "height": 800,
        "alt_text": f"Asset {asset_id}",
    }


def _ctx() -> TranspileContext:
    return TranspileContext(project_id=1, page_id=1, page_lang="es", asset_resolver=_resolver)


def test_empty_page_produces_empty_content() -> None:
    result = transpile_page([], _ctx())
    assert result.content == []
    assert result.residuals == []


def test_transpile_result_incluye_theme_styles_global() -> None:
    """C.6 — TranspileResult.theme_styles_global se rellena siempre
    (incluso sin theme_styles del origen → paleta Webcafeína default)."""
    result = transpile_page([], _ctx())
    assert result.theme_styles_global is not None
    assert len(result.theme_styles_global.colorPalette) >= 4


def test_transpile_result_theme_global_usa_paleta_origen() -> None:
    """C.6 — Si TranspileContext.theme_styles trae el formato C.3,
    la paleta global usa esos colores en vez del default."""
    ctx = TranspileContext(
        project_id=1, page_id=1, page_lang="es", asset_resolver=_resolver,
        theme_styles={
            "colors": {
                "primary": "#0e1218",
                "bg": "#1a222d",
                "text": "#e2e8f0",
                "accent": "#b1f100",
            },
            "typography": {"body": {"font-family": "Inter"}, "h1": {"font-family": "Inter"}},
        },
    )
    result = transpile_page([], ctx)
    names = {c.name for c in result.theme_styles_global.colorPalette}
    assert names == {"primary", "bg", "text", "accent"}
    accent = next(c for c in result.theme_styles_global.colorPalette if c.name == "accent")
    assert accent.color == "#b1f100"


def test_single_hero_block_validates() -> None:
    blocks = [
        {
            "order_index": 0,
            "block_type": BlockType.HERO,
            "content_json": {
                "headline": "Hola",
                "subheadline": "Mundo",
                "cta_text": "Pulsa",
                "cta_url": "/pulsa",
            },
        }
    ]
    result = transpile_page(blocks, _ctx())
    validation = validate_bricks_page(result.content)
    assert validation.is_valid, f"Errores: {validation.errors}"
    # hero ya emite su propia section, no debería envolverse extra
    assert sum(1 for el in result.content if el["name"] == "section") == 1


def test_atomic_text_gets_wrapped_in_section() -> None:
    blocks = [
        {
            "order_index": 0,
            "block_type": BlockType.TEXT,
            "content_json": {"html": "<p>Solo texto</p>"},
        }
    ]
    result = transpile_page(blocks, _ctx())
    validation = validate_bricks_page(result.content)
    assert validation.is_valid, f"Errores: {validation.errors}"
    names = [el["name"] for el in result.content]
    # wrap section + wrap container + el text original
    assert names == ["section", "container", "text"]


def test_multiple_blocks_each_wrapped_independently() -> None:
    blocks = [
        {"order_index": 0, "block_type": BlockType.HEADING,
         "content_json": {"level": "h2", "text": "T1"}},
        {"order_index": 1, "block_type": BlockType.TEXT,
         "content_json": {"html": "<p>P1</p>"}},
        {"order_index": 2, "block_type": BlockType.HEADING,
         "content_json": {"level": "h2", "text": "T2"}},
    ]
    result = transpile_page(blocks, _ctx())
    validation = validate_bricks_page(result.content)
    assert validation.is_valid, f"Errores: {validation.errors}"

    sections = [el for el in result.content if el["name"] == "section"]
    assert len(sections) == 3, "Cada bloque atómico debe envolverse en su propia section"


def test_unknown_block_does_not_pollute_content_but_records_residual() -> None:
    blocks = [
        {"order_index": 0, "block_type": BlockType.UNKNOWN,
         "content_json": {"notes": "wix-velo-custom-widget"}},
    ]
    result = transpile_page(blocks, _ctx())
    assert result.content == []
    assert len(result.residuals) == 1
    assert "Reconstruir manualmente" in result.residuals[0].description


def test_transpile_is_deterministic_run_twice() -> None:
    blocks = [
        {"order_index": 0, "block_type": BlockType.HERO,
         "content_json": {"headline": "X", "cta_text": "Go", "cta_url": "/"}},
        {"order_index": 1, "block_type": BlockType.FAQ,
         "content_json": {"items": [{"q": "Q", "a": "A"}]}},
    ]
    r1 = transpile_page(blocks, _ctx())
    r2 = transpile_page(blocks, _ctx())
    assert r1.content == r2.content, "Transpile no es determinista"


def test_blocks_sorted_by_order_index() -> None:
    blocks = [
        {"order_index": 2, "block_type": BlockType.HEADING,
         "content_json": {"level": "h2", "text": "Tercero"}},
        {"order_index": 0, "block_type": BlockType.HEADING,
         "content_json": {"level": "h2", "text": "Primero"}},
        {"order_index": 1, "block_type": BlockType.HEADING,
         "content_json": {"level": "h2", "text": "Segundo"}},
    ]
    result = transpile_page(blocks, _ctx())
    # Encontrar los heading elements y verificar orden por su texto
    headings = [el for el in result.content if el["name"] == "heading"]
    assert headings[0]["settings"]["text"] == "Primero"
    assert headings[1]["settings"]["text"] == "Segundo"
    assert headings[2]["settings"]["text"] == "Tercero"


def test_full_page_with_diverse_blocks_validates() -> None:
    blocks = [
        {"order_index": 0, "block_type": BlockType.HERO,
         "content_json": {"headline": "H", "subheadline": "S", "cta_text": "C", "cta_url": "/c"}},
        {"order_index": 1, "block_type": BlockType.TEXT,
         "content_json": {"html": "<p>texto</p>"}},
        {"order_index": 2, "block_type": BlockType.IMAGE,
         "content_json": {"asset_id": 42, "alt": "img"}},
        {"order_index": 3, "block_type": BlockType.GALLERY,
         "content_json": {"asset_ids": [1, 2, 3], "layout": "grid", "cols": 3}},
        {"order_index": 4, "block_type": BlockType.FAQ,
         "content_json": {"items": [{"q": "x", "a": "y"}]}},
        {"order_index": 5, "block_type": BlockType.DIVIDER,
         "content_json": {"style": "space", "size": "32px"}},
        {"order_index": 6, "block_type": BlockType.FORM,
         "content_json": {"gf_form_id": 1}},
        {"order_index": 7, "block_type": BlockType.VIDEO,
         "content_json": {"provider": "youtube", "url_or_id": "abc"}},
        {"order_index": 8, "block_type": BlockType.TESTIMONIAL,
         "content_json": {"quote": "Q", "author": "A"}},
    ]
    result = transpile_page(blocks, _ctx())
    validation = validate_bricks_page(result.content)
    assert validation.is_valid, f"Errores: {validation.errors}"
    assert result.residuals == [], f"Residuales inesperados: {result.residuals}"
