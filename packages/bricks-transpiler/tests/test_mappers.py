"""Tests por mapper — entrada ContentBlock-like → salida BricksElement esperada."""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.mappers import (
    MapperContext,
    get_mapper,
)
from wcm_types.enums import BlockType


def _stub_resolver(asset_id: int) -> dict[str, Any]:
    return {
        "url": f"/wp-content/uploads/asset-{asset_id}.webp",
        "wp_attachment_id": 1000 + asset_id,
        "width": 1200,
        "height": 800,
        "alt_text": f"Asset {asset_id}",
    }


def _ctx() -> MapperContext:
    return MapperContext(
        project_id=1, page_id=1, page_lang="es",
        id_gen=IdGenerator(project_id=1, page_id=1),
        asset_resolver=_stub_resolver,
    )


def test_heading_basic() -> None:
    mapper = get_mapper(BlockType.HEADING)
    res = mapper({"level": "h2", "text": "Hola"}, 0, BlockType.HEADING, "con001", _ctx())
    assert res.residual is None
    assert len(res.elements) == 1
    el = res.elements[0]
    assert el.name == "heading"
    assert el.settings["tag"] == "h2"
    assert el.settings["text"] == "Hola"


def test_text_with_richtext_html() -> None:
    mapper = get_mapper(BlockType.TEXT)
    res = mapper({"html": "<p>foo</p>"}, 0, BlockType.TEXT, "con001", _ctx())
    el = res.elements[0]
    assert el.name == "text"
    assert el.settings["text"] == "<p>foo</p>"


def test_image_without_asset_id_is_residual() -> None:
    mapper = get_mapper(BlockType.IMAGE)
    res = mapper({}, 0, BlockType.IMAGE, "con001", _ctx())
    assert res.elements == []
    assert res.residual is not None
    assert "asset_id" in res.residual.description


def test_image_with_asset_uses_resolver() -> None:
    mapper = get_mapper(BlockType.IMAGE)
    res = mapper({"asset_id": 42, "alt": "Foto"}, 0, BlockType.IMAGE, "con001", _ctx())
    el = res.elements[0]
    assert el.name == "image"
    img = el.settings["image"]
    assert img["url"] == "/wp-content/uploads/asset-42.webp"
    assert img["id"] == 1042
    assert img["alt"] == "Foto"


def test_cta_primary_styles() -> None:
    mapper = get_mapper(BlockType.CTA)
    res = mapper(
        {"text": "Contacta", "url": "https://webcafeina.com/contacto", "style": "primary"},
        0, BlockType.CTA, "con001", _ctx(),
    )
    el = res.elements[0]
    assert el.name == "button"
    assert el.settings["link"]["type"] == "external"
    # Acento lima debe ir como bg-color
    assert el.settings["_background"]["color"]["raw"] == "var(--accent)"


def test_hero_full_emits_section_container_heading_text_button() -> None:
    mapper = get_mapper(BlockType.HERO)
    res = mapper(
        {
            "headline": "Migra tu web",
            "subheadline": "En menos de 90 minutos",
            "cta_text": "Empieza",
            "cta_url": "/contacto/",
        },
        0, BlockType.HERO, "0", _ctx(),
    )
    names = [e.name for e in res.elements]
    assert names == ["section", "container", "heading", "text", "button"]
    section = res.elements[0]
    container = res.elements[1]
    assert section.parent == "0"
    assert section.children == [container.id]
    # container.children debe listar heading, text, button
    assert len(container.children) == 3


def test_hero_only_headline_omits_text_and_button() -> None:
    mapper = get_mapper(BlockType.HERO)
    res = mapper({"headline": "Solo título"}, 0, BlockType.HERO, "0", _ctx())
    names = [e.name for e in res.elements]
    assert names == ["section", "container", "heading"]


def test_divider_space_becomes_spacer() -> None:
    mapper = get_mapper(BlockType.DIVIDER)
    res = mapper({"style": "space", "size": "48px"}, 0, BlockType.DIVIDER, "con001", _ctx())
    el = res.elements[0]
    assert el.name == "spacer"
    assert el.settings["height"] == "48px"


def test_divider_line_becomes_divider() -> None:
    mapper = get_mapper(BlockType.DIVIDER)
    res = mapper({"style": "line"}, 0, BlockType.DIVIDER, "con001", _ctx())
    el = res.elements[0]
    assert el.name == "divider"


def test_faq_to_accordion() -> None:
    mapper = get_mapper(BlockType.FAQ)
    res = mapper(
        {"items": [{"q": "¿Cuánto tarda?", "a": "90 minutos"}, {"q": "¿Coste?", "a": "Variable"}]},
        0, BlockType.FAQ, "con001", _ctx(),
    )
    el = res.elements[0]
    assert el.name == "accordion"
    assert len(el.settings["items"]) == 2
    assert el.settings["items"][0]["title"] == "¿Cuánto tarda?"


def test_faq_empty_is_residual() -> None:
    mapper = get_mapper(BlockType.FAQ)
    res = mapper({}, 0, BlockType.FAQ, "con001", _ctx())
    assert res.elements == []
    assert res.residual is not None


def test_gallery_grid_becomes_image_gallery() -> None:
    mapper = get_mapper(BlockType.GALLERY)
    res = mapper(
        {"asset_ids": [1, 2, 3], "layout": "grid", "cols": 3},
        0, BlockType.GALLERY, "con001", _ctx(),
    )
    el = res.elements[0]
    assert el.name == "image-gallery"
    assert el.settings["columns"] == 3
    assert len(el.settings["images"]) == 3


def test_gallery_carousel_becomes_slider_nested() -> None:
    mapper = get_mapper(BlockType.GALLERY)
    res = mapper(
        {"asset_ids": [1, 2], "layout": "carousel"},
        0, BlockType.GALLERY, "con001", _ctx(),
    )
    el = res.elements[0]
    assert el.name == "slider-nested"


def test_form_without_gf_id_is_residual() -> None:
    mapper = get_mapper(BlockType.FORM)
    res = mapper({}, 0, BlockType.FORM, "con001", _ctx())
    assert res.elements == []
    assert res.residual is not None


def test_form_with_gf_id_becomes_shortcode() -> None:
    mapper = get_mapper(BlockType.FORM)
    res = mapper({"gf_form_id": 7}, 0, BlockType.FORM, "con001", _ctx())
    el = res.elements[0]
    assert el.name == "shortcode"
    assert 'id="7"' in el.settings["shortcode"]


def test_video_youtube_becomes_video_element() -> None:
    mapper = get_mapper(BlockType.VIDEO)
    res = mapper(
        {"provider": "youtube", "url_or_id": "dQw4w9WgXcQ"},
        0, BlockType.VIDEO, "con001", _ctx(),
    )
    el = res.elements[0]
    assert el.name == "video"
    assert el.settings["provider"] == "youtube"


def test_video_selfhost_is_residual() -> None:
    mapper = get_mapper(BlockType.VIDEO)
    res = mapper(
        {"provider": "selfhost", "url_or_id": "https://origen/video.mp4"},
        0, BlockType.VIDEO, "con001", _ctx(),
    )
    assert res.elements == []
    assert res.residual is not None


def test_unknown_always_residual() -> None:
    mapper = get_mapper(BlockType.UNKNOWN)
    res = mapper({"notes": "wix-special-component"}, 0, BlockType.UNKNOWN, "con001", _ctx())
    assert res.elements == []
    assert res.residual is not None
    assert "Reconstruir manualmente" in res.residual.description


def test_testimonial_with_quote_and_author() -> None:
    mapper = get_mapper(BlockType.TESTIMONIAL)
    res = mapper(
        {"quote": "Gran servicio.", "author": "Ana", "role": "CEO"},
        0, BlockType.TESTIMONIAL, "con001", _ctx(),
    )
    names = [e.name for e in res.elements]
    # block (root) + text (quote) + text-basic (author)
    assert names[0] == "block"
    assert "text" in names
    assert "text-basic" in names


# B.7 — map_grid (Wix repeater → section + container + N cards)


def test_grid_empty_is_residual() -> None:
    mapper = get_mapper(BlockType.GRID)
    res = mapper({"items": []}, 0, BlockType.GRID, "0", _ctx())
    assert res.elements == []
    assert res.residual is not None
    assert "Grid vacío" in res.residual.title


def test_grid_three_items_full() -> None:
    """3 items con image + heading + link → section + container + 3 cards
    (cada card: block + image + heading + button)."""
    mapper = get_mapper(BlockType.GRID)
    res = mapper(
        {
            "items": [
                {"image_url": "https://cdn/i1.png", "heading": "A", "link": "/a"},
                {"image_url": "https://cdn/i2.png", "heading": "B", "link": "/b"},
                {"image_url": "https://cdn/i3.png", "heading": "C", "link": "/c"},
            ]
        },
        0, BlockType.GRID, "0", _ctx(),
    )
    names = [e.name for e in res.elements]
    # 1 section + 1 container + 3 (block) + 3 (image) + 3 (heading) + 3 (button) = 14
    assert names[0] == "section"
    assert names[1] == "container"
    assert names.count("block") == 3
    assert names.count("image") == 3
    assert names.count("heading") == 3
    assert names.count("button") == 3
    assert len(res.elements) == 14

    # Heading interno usa h3 + el texto correcto.
    headings = [e for e in res.elements if e.name == "heading"]
    assert headings[0].settings["text"] == "A"
    assert headings[0].settings["tag"] == "h3"

    # Image external.
    images = [e for e in res.elements if e.name == "image"]
    assert images[0].settings["image"]["external"] is True
    assert images[0].settings["image"]["url"] == "https://cdn/i1.png"


def test_grid_item_solo_heading_no_emite_image_ni_button() -> None:
    """Item sin image_url y sin link → solo block + heading (sin image, sin button)."""
    mapper = get_mapper(BlockType.GRID)
    res = mapper(
        {"items": [{"heading": "Title only"}]},
        0, BlockType.GRID, "0", _ctx(),
    )
    names = [e.name for e in res.elements]
    # 1 section + 1 container + 1 block + 1 heading = 4
    assert names == ["section", "container", "block", "heading"]


def test_grid_container_es_flex_row_wrap() -> None:
    """El container debe usar layout flex row con wrap para grid responsive."""
    mapper = get_mapper(BlockType.GRID)
    res = mapper(
        {"items": [{"heading": "x"}]},
        0, BlockType.GRID, "0", _ctx(),
    )
    container = next(e for e in res.elements if e.name == "container")
    assert container.settings["_direction"] == "row"
    assert container.settings["_flexWrap"] == "wrap"
    assert container.settings["_gap"] == "32px"


def test_grid_cards_son_terceras_partes() -> None:
    """Width de cada card = calc((100% - 64px) / 3) → 3 columnas con gap 32."""
    mapper = get_mapper(BlockType.GRID)
    res = mapper(
        {"items": [{"heading": str(i)} for i in range(3)]},
        0, BlockType.GRID, "0", _ctx(),
    )
    cards = [e for e in res.elements if e.name == "block"]
    for card in cards:
        assert card.settings["_width"] == "calc((100% - 64px) / 3)"


def test_pricing_with_two_tiers() -> None:
    mapper = get_mapper(BlockType.PRICING)
    res = mapper(
        {
            "tiers": [
                {"name": "Basic", "price": "29€", "period": "/mes", "features": ["10 GB"],
                 "cta": {"text": "Empezar", "url": "/basic"}},
                {"name": "Pro", "price": "99€", "period": "/mes", "features": ["100 GB"],
                 "cta": {"text": "Empezar", "url": "/pro"}},
            ]
        },
        0, BlockType.PRICING, "con001", _ctx(),
    )
    container_el = res.elements[0]
    assert container_el.name == "container"
    # Hay 2 tiers, cada uno con un block + heading + text-basic + text + button = 4 hijos.
    # En total: 1 container + 2 (block) + 2 (heading) + 2 (price) + 2 (features) + 2 (cta) = 11
    assert len(res.elements) == 11
