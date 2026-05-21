"""Orquestador principal del transpilador.

Entrada: lista de content_blocks de UNA página + contexto del proyecto.
Salida: array de elementos Bricks listos para `_bricks_page_content_2` +
hints de tareas residuales.

`transpile_page` envuelve cada bloque en una `section + container` raíz
si el mapper devuelve elementos atómicos top-level (sin section propia).
Los mappers compuestos (hero, footer, pricing) ya emiten su propia
section/container y se insertan tal cual.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.mappers import MapperContext, MapperResult, get_mapper
from wcm_bricks_transpiler.mappers._types import ResidualHint
from wcm_bricks_transpiler.schema import (
    BRICKS_SCHEMA_VERSION,
    BricksElement,
    BricksThemeStyles,
)
from wcm_bricks_transpiler.theme import build_theme_styles
from wcm_types.enums import BlockType


@dataclass
class TranspileContext:
    """Contexto de una página a transpilar."""

    project_id: int
    page_id: int
    page_lang: str | None = None
    #: Función que dado un asset_id (BD) devuelve dict con `url`,
    #: `wp_attachment_id` (si aplica), `width`, `height`, `alt_text`.
    asset_resolver: Callable[[int], dict[str, Any]] = field(
        default=lambda asset_id: {"url": f"/wp-content/uploads/asset-{asset_id}.webp"}
    )
    #: C.4 (2026-05-21) — Theme Styles sintetizados por el agente
    #: `theme_styles`. Si es None, los mappers usan defaults Bricks.
    theme_styles: dict[str, Any] | None = None


@dataclass
class TranspileResult:
    """Output de transpile_page.

    `content` es el array que entra en `bricks_pages.bricks_json`.
    `residuals` se transforma en filas de `residual_tasks` por el
    bricks-transpiler agente (no por este paquete).
    `theme_styles_global` (C.6) — Bricks Theme Styles globales que
    deben aplicarse al sitio (opción WP `bricks_global_settings`). El
    agente bricks-transpiler los persiste una sola vez por proyecto.
    """

    content: list[dict[str, Any]] = field(default_factory=list)
    residuals: list[ResidualHint] = field(default_factory=list)
    schema_version: str = BRICKS_SCHEMA_VERSION
    theme_styles_global: BricksThemeStyles | None = None


def _wrap_in_section(
    block_elements: list[BricksElement],
    order_index: int,
    ctx: MapperContext,
    block_label: str,
) -> list[BricksElement]:
    """Envuelve los elementos de un bloque en una section + container raíz.

    Necesario porque Bricks no permite elementos atómicos ni block/container
    huérfanos directamente en top-level — deben vivir dentro de section.

    Solo se re-parenta el PRIMER elemento (root del bloque); los demás ya
    tienen sus relaciones internas correctas y deben preservarse.
    """
    section_id = ctx.id_gen.fresh(order_index, f"wrap-{block_label}", sub_index=0)
    container_id = ctx.id_gen.fresh(order_index, f"wrap-{block_label}", sub_index=1)

    # Identificar los "roots" del bloque: elementos con parent="0".
    # Normalmente solo el primero, pero en testimonial/pricing los blocks hijos
    # ya tienen un parent local; los roots son los que apuntaban a "0".
    roots = [el for el in block_elements if el.parent == "0"]
    if not roots:
        # Mapper devolvió elementos pero ninguno top-level — anomalía, devolver tal cual.
        return block_elements

    for root in roots:
        root.parent = container_id

    section = BricksElement(
        id=section_id, name="section", parent="0", children=[container_id],
        settings={
            "_padding": {"top": "40px", "right": "24px", "bottom": "40px", "left": "24px"},
        },
        label=block_label.capitalize(),
    )
    container = BricksElement(
        id=container_id, name="container", parent=section_id,
        children=[r.id for r in roots], settings={},
    )

    return [section, container, *block_elements]


def transpile_page(
    content_blocks: list[dict[str, Any]],
    ctx: TranspileContext,
) -> TranspileResult:
    """Transpila una página completa.

    `content_blocks` es una lista de dicts con al menos las keys:
    - `order_index: int`
    - `block_type: BlockType | str`
    - `content_json: dict`
    - `lang: str | None`
    Normalmente vienen de SQLAlchemy `ContentBlock.__dict__` o de un dump JSON.

    El orden de aparición en la página = orden por `order_index` ascendente.
    """
    sorted_blocks = sorted(content_blocks, key=lambda b: b["order_index"])

    id_gen = IdGenerator(project_id=ctx.project_id, page_id=ctx.page_id)
    mapper_ctx = MapperContext(
        project_id=ctx.project_id,
        page_id=ctx.page_id,
        page_lang=ctx.page_lang,
        id_gen=id_gen,
        asset_resolver=ctx.asset_resolver,
        theme_styles=ctx.theme_styles,
    )

    final_elements: list[BricksElement] = []
    residuals: list[ResidualHint] = []

    for raw_block in sorted_blocks:
        order_index = raw_block["order_index"]
        raw_type = raw_block["block_type"]
        block_type = raw_type if isinstance(raw_type, BlockType) else BlockType(raw_type)
        content = raw_block.get("content_json") or {}

        mapper = get_mapper(block_type)
        result: MapperResult = mapper(
            content, order_index, block_type, "0", mapper_ctx,
        )

        if result.residual is not None:
            residuals.append(result.residual)

        if not result.elements:
            continue

        first = result.elements[0]
        # Si el mapper emitió una section top-level, insertar tal cual.
        # Cualquier otro caso (atómicos, block, container, accordion, ...) se
        # envuelve en section + container raíz para mantener la jerarquía Bricks.
        if first.name == "section" and first.parent == "0":
            final_elements.extend(result.elements)
        else:
            wrapped = _wrap_in_section(
                result.elements, order_index, mapper_ctx, block_type.value,
            )
            final_elements.extend(wrapped)

    content_json = [el.model_dump(exclude_none=True) for el in final_elements]
    # C.6 — generar Theme Styles globales para el sitio destino. Si no
    # hay theme sintetizado, build_theme_styles() devuelve la paleta
    # Webcafeína corporativa por defecto, lo cual sigue siendo mejor
    # que los defaults Bricks "vainilla".
    theme_global = build_theme_styles(ctx.theme_styles)
    return TranspileResult(
        content=content_json,
        residuals=residuals,
        theme_styles_global=theme_global,
    )
