"""Mappers para bloques atómicos (1 ContentBlock → 1 BricksElement)."""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler.mappers._styling import styles_inline_or_class
from wcm_bricks_transpiler.mappers._types import (
    MapperContext,
    MapperResult,
    ResidualHint,
)
from wcm_bricks_transpiler.schema import BricksElement
from wcm_types.enums import BlockType


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    """Quita keys con valor None — Bricks prefiere ausencia a null explícito."""
    return {k: v for k, v in d.items() if v is not None}


def _apply_element_styles(
    settings: dict[str, Any],
    block: dict[str, Any],
    ctx: MapperContext,
    *,
    prefix: str,
) -> None:
    """v0.23.0 — aplica `block["element_styles"]` (computed del origen)
    a `settings` como inline o globalClass, según riqueza."""
    element_styles = block.get("element_styles")
    if not element_styles:
        return
    inline, global_classes = styles_inline_or_class(
        element_styles, prefix=prefix, ctx=ctx
    )
    # Merge inline (no sobrescribe values explícitos del block).
    for k, v in inline.items():
        if k in ("_typography", "_padding", "_background", "_border", "_layout") and isinstance(v, dict):
            settings.setdefault(k, {}).update(v)
        else:
            settings.setdefault(k, v)
    if global_classes:
        existing = settings.get("_cssGlobalClasses") or []
        settings["_cssGlobalClasses"] = list({*existing, *global_classes})


# ---------- heading ----------

def map_heading(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    settings: dict[str, Any] = {
        "tag": block.get("level", "h2"),
        "text": block.get("text", ""),
    }
    if (align := block.get("align")) is not None:
        settings.setdefault("_typography", {})["text-align"] = align

    _apply_element_styles(settings, block, ctx, prefix=f"h-{block.get('level', 'h2')}")

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "heading"),
        name="heading",
        parent=parent_id,
        settings=settings,
    )
    return MapperResult(elements=[el])


# ---------- text ----------

def map_text(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    settings: dict[str, Any] = {
        "text": block.get("html", block.get("text", "")),
    }
    if (align := block.get("align")) is not None:
        settings.setdefault("_typography", {})["text-align"] = align

    _apply_element_styles(settings, block, ctx, prefix="text")

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "text"),
        name="text",
        parent=parent_id,
        settings=settings,
    )
    return MapperResult(elements=[el])


# ---------- image ----------

def map_image(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    asset_id = block.get("asset_id")
    if asset_id is None:
        return MapperResult(
            residual=ResidualHint(
                title=f"Bloque image sin asset_id (orden {order_index})",
                description="El content-extractor produjo un bloque image sin asset_id resoluble. Revisar el scraping origen.",
                estimated_minutes=10,
            )
        )

    asset = ctx.asset_resolver(asset_id)
    image_settings: dict[str, Any] = _strip_none(
        {
            "id": asset.get("wp_attachment_id"),
            "url": asset.get("url"),
            "alt": block.get("alt") or asset.get("alt_text"),
            "width": block.get("width") or asset.get("width"),
            "height": block.get("height") or asset.get("height"),
        }
    )

    settings: dict[str, Any] = {"image": image_settings}
    if (caption := block.get("caption")) is not None:
        settings["caption"] = caption

    _apply_element_styles(settings, block, ctx, prefix="img")

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "image"),
        name="image",
        parent=parent_id,
        settings=settings,
    )
    return MapperResult(elements=[el])


# ---------- cta (button) ----------

def map_cta(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    style = block.get("style", "primary")
    settings: dict[str, Any] = {
        "text": block.get("text", ""),
        "link": _strip_none(
            {
                "type": "external" if str(block.get("url", "")).startswith("http") else "internal",
                "url": block.get("url", "#"),
                "target": block.get("target"),
            }
        ),
        "style": style,
    }
    # Aplicar variantes de marca: primary usa accent (lima), secondary usa borde.
    # Si el bloque trae `element_styles` del origen, lo apply override
    # estos defaults para reproducir el botón original.
    if style == "primary":
        settings["_background"] = {"color": {"raw": "var(--bricks-color-accent)"}}
        settings["_typography"] = {"color": {"raw": "var(--bricks-color-primary)"}, "font-weight": "600"}
    else:
        settings["_border"] = {
            "width": {"top": "1px", "right": "1px", "bottom": "1px", "left": "1px"},
            "style": "solid",
            "color": {"raw": "var(--bricks-color-text)"},
        }

    _apply_element_styles(settings, block, ctx, prefix="cta")

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "button"),
        name="button",
        parent=parent_id,
        settings=settings,
    )
    return MapperResult(elements=[el])


# ---------- divider ----------

def map_divider(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    style = block.get("style", "line")
    if style == "space":
        el = BricksElement(
            id=ctx.id_gen.fresh(order_index, "spacer"),
            name="spacer",
            parent=parent_id,
            settings={"height": block.get("size", "32px")},
        )
    else:
        el = BricksElement(
            id=ctx.id_gen.fresh(order_index, "divider"),
            name="divider",
            parent=parent_id,
            settings={
                "style": "solid",
                "color": {"raw": "var(--detail-brown)"},
                "height": block.get("size", "1px"),
            },
        )
    return MapperResult(elements=[el])


# ---------- video ----------

def map_video(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    provider = block.get("provider", "youtube")
    url_or_id = block.get("url_or_id") or block.get("url") or block.get("id")

    if provider == "selfhost":
        # MVP: no rehosteamos vídeos. Tarea residual obligatoria.
        return MapperResult(
            residual=ResidualHint(
                title=f"Vídeo self-host pendiente de rehospedar (orden {order_index})",
                description=(
                    f"El origen embebe un vídeo alojado en el propio sitio ({url_or_id}). "
                    "Subir a YouTube/Vimeo del cliente y actualizar el enlace antes del go-live."
                ),
                estimated_minutes=30,
            )
        )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "video"),
        name="video",
        parent=parent_id,
        settings=_strip_none(
            {
                "provider": provider,
                "videoId": url_or_id,
                "autoplay": block.get("autoplay", False),
                "controls": block.get("controls", True),
            }
        ),
    )
    return MapperResult(elements=[el])


# ---------- embed ----------

def map_embed(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    html = block.get("html", "")
    if not html:
        return MapperResult(
            residual=ResidualHint(
                title=f"Bloque embed vacío (orden {order_index})",
                description="El content-extractor identificó un embed sin contenido HTML resoluble.",
                estimated_minutes=15,
            )
        )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "code"),
        name="code",
        parent=parent_id,
        settings={"code": html, "executeCode": False},
    )
    return MapperResult(elements=[el])
