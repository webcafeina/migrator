"""Mapper para bloques generados por Claude Vision (BlockType.AI_GENERATED).

Sprint v0.22.0 — AI.4 produce content_blocks con
`content_json = {"bricks_elements": [...], "notes": "..."}`. El mapper
los pasa al output tal cual, regenerando IDs si chocan con IDs ya
usados por otros mappers en la misma página (cosa que pasa porque
Claude no sabe qué IDs hemos generado para los demás bloques).
"""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler.mappers._types import (
    MapperContext,
    MapperResult,
    ResidualHint,
)
from wcm_bricks_transpiler.schema import BricksElement
from wcm_types.enums import BlockType


def map_ai_generated(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Toma `block["bricks_elements"]` y los emite como elementos Bricks.

    Reasigna IDs vía `ctx.id_gen` para evitar colisión con otros bloques
    de la misma página. Mantiene la jerarquía interna del array original
    (mapping `old_id → new_id` para reescribir parents y children).

    Si `bricks_elements` está vacío o malformado, emite residual.
    """
    raw_elements: list[dict[str, Any]] = block.get("bricks_elements") or []
    if not isinstance(raw_elements, list) or not raw_elements:
        return MapperResult(
            residual=ResidualHint(
                title=f"Bloque AI_GENERATED vacío (orden {order_index})",
                description=(
                    "El bloque generado por Claude no tiene `bricks_elements` "
                    "o está malformado. Revisar log de ai_assist + cache "
                    "ai_section_cache. Posible causa: tool_use devolvió "
                    "array vacío en una sección invisible."
                ),
                estimated_minutes=5,
            )
        )

    # Mapping old_id → new_id para reescribir referencias.
    id_map: dict[str, str] = {}
    for idx, elem in enumerate(raw_elements):
        old_id = elem.get("id")
        if not isinstance(old_id, str):
            continue
        new_id = ctx.id_gen.fresh(order_index, "ai", sub_index=idx)
        id_map[old_id] = new_id

    output: list[BricksElement] = []
    residuals: list[ResidualHint] = []
    for elem in raw_elements:
        old_id = elem.get("id")
        if not isinstance(old_id, str) or old_id not in id_map:
            # Sin id válido → skip individual con residual + continue.
            residuals.append(
                ResidualHint(
                    title=f"Elemento AI sin id válido (orden {order_index})",
                    description=(
                        f"Elemento ignorado por id inválido: "
                        f"{str(elem.get('id'))[:80]!r}. El resto del "
                        "bloque sigue procesándose."
                    ),
                    estimated_minutes=2,
                )
            )
            continue

        new_id = id_map[old_id]
        old_parent = elem.get("parent")
        if old_parent == "0":
            new_parent = parent_id  # top-level del bloque
        elif isinstance(old_parent, str) and old_parent in id_map:
            new_parent = id_map[old_parent]
        else:
            # Parent desconocido → ancla al parent del bloque.
            new_parent = parent_id

        new_children: list[str] = []
        for cid in elem.get("children") or []:
            if isinstance(cid, str) and cid in id_map:
                new_children.append(id_map[cid])

        try:
            output.append(
                BricksElement(
                    id=new_id,
                    name=elem.get("name", "block"),
                    parent=new_parent,
                    children=new_children,
                    settings=elem.get("settings") or {},
                    label=elem.get("label"),
                )
            )
        except Exception as e:  # noqa: BLE001 — validación pydantic falla
            # Claude devolvió algo que no pasa validator → residual y
            # continúa con los demás elementos.
            residuals.append(
                ResidualHint(
                    title=f"Elemento AI inválido (orden {order_index})",
                    description=(
                        f"Elemento {elem.get('name', '?')!r} rechazado por "
                        f"validator Bricks: {str(e)[:200]}. El bloque puede "
                        "quedar parcial."
                    ),
                    estimated_minutes=5,
                )
            )
            continue

    if not output:
        return MapperResult(
            residual=ResidualHint(
                title=f"Bloque AI sin elementos válidos (orden {order_index})",
                description=(
                    "Todos los elementos devueltos por Claude fueron "
                    "rechazados por el validator. Revisar prompt del "
                    "ai_assist o ampliar BRICKS_ELEMENT_NAMES."
                ),
                estimated_minutes=15,
            )
        )

    # Devolver el primer residual encontrado (si hay) + elementos válidos.
    return MapperResult(
        elements=output,
        residual=residuals[0] if residuals else None,
    )
