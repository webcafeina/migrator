"""Registry de mappers ContentBlock → list[BricksElement].

Cada mapper se registra por `BlockType` y produce uno o más elementos
Bricks que se insertan en el array de la página. Si un mapper devuelve
`MapperResult.residual`, el bloque no se puede migrar y `transpile_page`
añade una tarea residual al output.
"""

from __future__ import annotations

from wcm_bricks_transpiler.mappers._types import BlockMapper, MapperContext, MapperResult
from wcm_bricks_transpiler.mappers.ai import map_ai_generated
from wcm_bricks_transpiler.mappers.atomic import (
    map_cta,
    map_divider,
    map_embed,
    map_heading,
    map_image,
    map_text,
    map_video,
)
from wcm_bricks_transpiler.mappers.composite import (
    map_faq,
    map_footer,
    map_form,
    map_gallery,
    map_grid,
    map_hero,
    map_nav,
    map_pricing,
    map_product_card,
    map_testimonial,
)
from wcm_bricks_transpiler.mappers.raw import map_raw_html
from wcm_bricks_transpiler.mappers.unknown import map_unknown
from wcm_types.enums import BlockType

REGISTRY: dict[BlockType, BlockMapper] = {
    BlockType.HERO: map_hero,
    BlockType.TEXT: map_text,
    BlockType.HEADING: map_heading,
    BlockType.IMAGE: map_image,
    BlockType.GALLERY: map_gallery,
    BlockType.CTA: map_cta,
    BlockType.FORM: map_form,
    BlockType.TESTIMONIAL: map_testimonial,
    BlockType.PRICING: map_pricing,
    BlockType.FAQ: map_faq,
    BlockType.PRODUCT_CARD: map_product_card,
    BlockType.VIDEO: map_video,
    BlockType.EMBED: map_embed,
    BlockType.DIVIDER: map_divider,
    BlockType.NAV: map_nav,
    BlockType.FOOTER: map_footer,
    BlockType.GRID: map_grid,
    BlockType.AI_GENERATED: map_ai_generated,
    BlockType.RAW_HTML: map_raw_html,
    BlockType.UNKNOWN: map_unknown,
}


def get_mapper(block_type: BlockType) -> BlockMapper:
    """Devuelve el mapper registrado o `map_unknown` como fallback."""
    return REGISTRY.get(block_type, map_unknown)


__all__ = [
    "BlockMapper",
    "MapperContext",
    "MapperResult",
    "REGISTRY",
    "get_mapper",
]
