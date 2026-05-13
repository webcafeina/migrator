"""Mapper para bloques que el content-extractor no supo clasificar.

Estos no se transpilan: simplemente generan tarea residual con captura.
"""

from __future__ import annotations

from typing import Any

from wcm_types.enums import BlockType

from wcm_bricks_transpiler.mappers._types import (
    MapperContext,
    MapperResult,
    ResidualHint,
)


def map_unknown(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    notes = block.get("notes") or "bloque sin clasificar"
    return MapperResult(
        residual=ResidualHint(
            title=f"Bloque sin mapping (orden {order_index})",
            description=(
                f"El content-extractor marcó este bloque como `unknown` ({notes}). "
                "Reconstruir manualmente en Bricks Builder a partir del HTML original "
                "del scraping. La captura del bloque origen se adjunta."
            ),
            estimated_minutes=30,
            screenshot_paths=block.get("screenshot_paths") or [],
        )
    )
