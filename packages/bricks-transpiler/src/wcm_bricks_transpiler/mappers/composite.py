"""Mappers para bloques compuestos (1 ContentBlock → N BricksElement)."""

from __future__ import annotations

from typing import Any

from wcm_bricks_transpiler.mappers._types import (
    MapperContext,
    MapperResult,
    ResidualHint,
)
from wcm_bricks_transpiler.mappers.atomic import _strip_none
from wcm_bricks_transpiler.schema import BricksElement, settings_with_breakpoint
from wcm_types.enums import BlockType


def _section_with_container(
    order_index: int,
    parent_id: str,
    ctx: MapperContext,
    *,
    block_label: str,
    bg_color: str | None = None,
    bg_image_url: str | None = None,
) -> tuple[BricksElement, BricksElement]:
    """Helper: crea un section top-level + container hijo. Devuelve (section, container).

    Los IDs son deterministas con sub_index=0 para section, sub_index=1 para container.
    """
    section_id = ctx.id_gen.fresh(order_index, block_label, sub_index=0)
    container_id = ctx.id_gen.fresh(order_index, block_label, sub_index=1)

    section_settings: dict[str, Any] = settings_with_breakpoint(
        {"_padding": {"top": "80px", "right": "24px", "bottom": "80px", "left": "24px"}},
        "tablet_portrait",
        {"_padding": {"top": "60px", "right": "20px", "bottom": "60px", "left": "20px"}},
    )
    section_settings = settings_with_breakpoint(
        section_settings,
        "mobile_portrait",
        {"_padding": {"top": "40px", "right": "16px", "bottom": "40px", "left": "16px"}},
    )
    if bg_color:
        section_settings["_background"] = {"color": {"raw": bg_color}}
    if bg_image_url:
        section_settings.setdefault("_background", {})["image"] = {
            "url": bg_image_url, "size": "cover", "position": "center", "repeat": "no-repeat"
        }

    section = BricksElement(
        id=section_id,
        name="section",
        parent=parent_id,  # debería ser "0" para top-level
        children=[container_id],
        settings=section_settings,
        label=block_label.capitalize(),
    )
    container = BricksElement(
        id=container_id,
        name="container",
        parent=section_id,
        children=[],  # se rellena con los hijos
        settings={},
    )
    return section, container


# ---------- hero ----------

def map_hero(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    bg_image_url: str | None = None
    if (bg_asset_id := block.get("bg_image_asset_id")) is not None:
        bg_image_url = ctx.asset_resolver(bg_asset_id).get("url")

    section, container = _section_with_container(
        order_index,
        parent_id,
        ctx,
        block_label="hero",
        bg_color=block.get("bg_color") or "var(--bricks-color-primary)",
        bg_image_url=bg_image_url,
    )

    container.settings["_typography"] = {
        "text-align": block.get("text_align", "center"),
        "color": {"raw": "var(--bricks-color-text)"},
    }

    elements: list[BricksElement] = [section, container]
    sub_index = 2  # 0 = section, 1 = container

    # Headline
    if (headline := block.get("headline")):
        hed_id = ctx.id_gen.fresh(order_index, "hero", sub_index=sub_index); sub_index += 1
        elements.append(
            BricksElement(
                id=hed_id, name="heading", parent=container.id,
                settings={
                    "tag": "h1", "text": headline,
                    "_typography": {"font-size": "var(--text-4xl)", "font-weight": "700"},
                },
            )
        )
        container.children.append(hed_id)

    # Subheadline
    if (subheadline := block.get("subheadline")):
        txt_id = ctx.id_gen.fresh(order_index, "hero", sub_index=sub_index); sub_index += 1
        elements.append(
            BricksElement(
                id=txt_id, name="text", parent=container.id,
                settings={
                    "text": f"<p>{subheadline}</p>",
                    "_margin": {"top": "16px", "bottom": "32px"},
                },
            )
        )
        container.children.append(txt_id)

    # CTA
    if (cta_text := block.get("cta_text")):
        btn_id = ctx.id_gen.fresh(order_index, "hero", sub_index=sub_index); sub_index += 1
        elements.append(
            BricksElement(
                id=btn_id, name="button", parent=container.id,
                settings={
                    "text": cta_text,
                    "link": {
                        "type": "external" if str(block.get("cta_url", "")).startswith("http") else "internal",
                        "url": block.get("cta_url", "#"),
                    },
                    "style": "primary",
                    "_background": {"color": {"raw": "var(--bricks-color-accent)"}},
                    "_typography": {"color": {"raw": "var(--bricks-color-primary)"}, "font-weight": "600"},
                    "_padding": {"top": "12px", "right": "32px", "bottom": "12px", "left": "32px"},
                    "_border": {"radius": {"top": "8px", "right": "8px", "bottom": "8px", "left": "8px"}},
                },
            )
        )
        container.children.append(btn_id)

    return MapperResult(elements=elements)


# ---------- gallery ----------

def map_gallery(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    asset_ids: list[int] = block.get("asset_ids") or []
    if not asset_ids:
        return MapperResult(
            residual=ResidualHint(
                title=f"Galería vacía (orden {order_index})",
                description="El bloque gallery no tiene asset_ids. Revisar scraping.",
                estimated_minutes=10,
            )
        )

    images = [_strip_none(ctx.asset_resolver(aid)) for aid in asset_ids]
    layout = block.get("layout", "grid")

    if layout == "carousel":
        # slider-nested requiere slides como containers anidados → MVP: usar slider-nested simple con images settings
        el = BricksElement(
            id=ctx.id_gen.fresh(order_index, "gallery"),
            name="slider-nested",
            parent=parent_id,
            settings={
                "images": images,
                "options": {
                    "autoplay": block.get("autoplay", False),
                    "loop": True,
                    "navigation": True,
                    "pagination": True,
                },
            },
        )
    else:
        el = BricksElement(
            id=ctx.id_gen.fresh(order_index, "gallery"),
            name="image-gallery",
            parent=parent_id,
            settings=_strip_none(
                {
                    "images": images,
                    "layout": layout,
                    "columns": block.get("cols") or block.get("columns") or 3,
                    "lightbox": True,
                }
            ),
        )
    return MapperResult(elements=[el])


# ---------- grid (B.7 — Wix repeater → grid de cards) ----------


def map_grid(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """B.7 — Repeater de Wix mapeado a section + container + N cards.

    Cada item produce un `block` con imagen (si la hay), heading y
    botón link. El layout queda como flex column por defecto en Bricks;
    el operador puede ajustarlo a grid de N columnas desde el editor.
    Si la URL de imagen es externa (CDN Wix o R2 no procesado), se usa
    como external image — el asset-optimizer no la habrá registrado si
    no estaba en `image_urls` global del extractor.
    """
    items = block.get("items") or []
    if not items:
        return MapperResult(
            residual=ResidualHint(
                title=f"Grid vacío (orden {order_index})",
                description=(
                    "El bloque grid (wix repeater) no tiene items. "
                    "Revisar scraping o estructura del repeater origen."
                ),
                estimated_minutes=10,
            )
        )

    section, container = _section_with_container(
        order_index, parent_id, ctx, block_label="grid",
    )
    container.settings["_direction"] = "row"
    container.settings["_flexWrap"] = "wrap"
    container.settings["_gap"] = "32px"

    elements: list[BricksElement] = [section, container]
    sub_index = 2

    for item in items:
        card_id = ctx.id_gen.fresh(order_index, "grid", sub_index=sub_index)
        sub_index += 1
        container.children.append(card_id)
        card = BricksElement(
            id=card_id,
            name="block",
            parent=container.id,
            children=[],
            settings={"_width": "calc((100% - 64px) / 3)"},
        )
        elements.append(card)

        if image_url := item.get("image_url"):
            img_id = ctx.id_gen.fresh(order_index, "grid", sub_index=sub_index)
            sub_index += 1
            card.children.append(img_id)
            elements.append(
                BricksElement(
                    id=img_id,
                    name="image",
                    parent=card_id,
                    settings={
                        "image": {"url": image_url, "external": True},
                    },
                )
            )

        if heading := item.get("heading"):
            h_id = ctx.id_gen.fresh(order_index, "grid", sub_index=sub_index)
            sub_index += 1
            card.children.append(h_id)
            elements.append(
                BricksElement(
                    id=h_id,
                    name="heading",
                    parent=card_id,
                    settings={"text": heading, "tag": "h3"},
                )
            )

        if link := item.get("link"):
            l_id = ctx.id_gen.fresh(order_index, "grid", sub_index=sub_index)
            sub_index += 1
            card.children.append(l_id)
            elements.append(
                BricksElement(
                    id=l_id,
                    name="button",
                    parent=card_id,
                    settings={
                        "text": "View",
                        "link": {"type": "external", "url": link},
                    },
                )
            )

    return MapperResult(elements=elements)


# ---------- form ----------

def map_form(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Forms se recrean con Gravity Forms y se embeben vía shortcode."""
    gf_form_id = block.get("gf_form_id") or block.get("form_schema_id")
    if gf_form_id is None:
        return MapperResult(
            residual=ResidualHint(
                title=f"Formulario sin Gravity Forms ID (orden {order_index})",
                description=(
                    "El bloque form se detectó pero aún no tiene Gravity Forms ID asignado. "
                    "forms-rebuilder debe ejecutarse antes que bricks-transpiler para que la "
                    "transpilación tenga el ID listo, o reasignar manualmente."
                ),
                estimated_minutes=15,
            )
        )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "form"),
        name="shortcode",
        parent=parent_id,
        settings={"shortcode": f'[gravityform id="{gf_form_id}" title="false" description="false"]'},
    )
    return MapperResult(elements=[el])


# ---------- testimonial ----------

def map_testimonial(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Testimonial = block contenedor con quote (text), author (heading), avatar (image opt)."""
    block_id = ctx.id_gen.fresh(order_index, "testimonial", sub_index=0)
    elements: list[BricksElement] = []

    children_ids: list[str] = []
    sub_index = 1

    if (quote := block.get("quote")):
        qid = ctx.id_gen.fresh(order_index, "testimonial", sub_index=sub_index); sub_index += 1
        elements.append(
            BricksElement(
                id=qid, name="text", parent=block_id,
                settings={
                    "text": f"<blockquote>{quote}</blockquote>",
                    "_typography": {"font-size": "var(--text-lg)", "font-style": "italic"},
                },
            )
        )
        children_ids.append(qid)

    if (author := block.get("author")):
        aid = ctx.id_gen.fresh(order_index, "testimonial", sub_index=sub_index); sub_index += 1
        author_text = author
        if (role := block.get("role")):
            author_text = f"{author} — {role}"
        elements.append(
            BricksElement(
                id=aid, name="text-basic", parent=block_id,
                settings={
                    "text": author_text,
                    "_typography": {"font-weight": "600", "color": {"raw": "var(--bricks-color-accent)"}},
                    "_margin": {"top": "12px"},
                },
            )
        )
        children_ids.append(aid)

    block_el = BricksElement(
        id=block_id, name="block", parent=parent_id, children=children_ids,
        settings={
            "_padding": {"top": "32px", "right": "32px", "bottom": "32px", "left": "32px"},
            "_background": {"color": {"raw": "var(--bricks-color-secondary)"}},
            "_border": {"radius": {"top": "12px", "right": "12px", "bottom": "12px", "left": "12px"}},
        },
    )
    return MapperResult(elements=[block_el, *elements])


# ---------- pricing ----------

def map_pricing(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Pricing = container con N blocks (uno por tier).

    MVP: layout simple grid; cada tier muestra name + price + features + cta.
    """
    tiers: list[dict[str, Any]] = block.get("tiers") or []
    if not tiers:
        return MapperResult(
            residual=ResidualHint(
                title=f"Tabla de precios sin tiers (orden {order_index})",
                description="El bloque pricing fue detectado pero sin tiers resolubles.",
                estimated_minutes=20,
            )
        )

    container_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=0)
    elements: list[BricksElement] = []
    children_ids: list[str] = []
    sub_index = 1

    for tier in tiers:
        tier_block_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=sub_index); sub_index += 1
        tier_children: list[str] = []

        # Nombre
        name_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=sub_index); sub_index += 1
        elements.append(
            BricksElement(
                id=name_id, name="heading", parent=tier_block_id,
                settings={"tag": "h3", "text": tier.get("name", "Plan")},
            )
        )
        tier_children.append(name_id)

        # Precio
        price_text = f"{tier.get('price', '')} {tier.get('period', '')}".strip()
        if price_text:
            price_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=sub_index); sub_index += 1
            elements.append(
                BricksElement(
                    id=price_id, name="text-basic", parent=tier_block_id,
                    settings={
                        "text": price_text,
                        "_typography": {"font-size": "var(--text-3xl)", "font-weight": "700",
                                        "color": {"raw": "var(--bricks-color-accent)"}},
                    },
                )
            )
            tier_children.append(price_id)

        # Features
        features: list[str] = tier.get("features") or []
        if features:
            feat_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=sub_index); sub_index += 1
            html_list = "<ul>" + "".join(f"<li>{f}</li>" for f in features) + "</ul>"
            elements.append(
                BricksElement(
                    id=feat_id, name="text", parent=tier_block_id,
                    settings={"text": html_list, "_margin": {"top": "16px", "bottom": "24px"}},
                )
            )
            tier_children.append(feat_id)

        # CTA
        cta = tier.get("cta") or {}
        if cta.get("text"):
            cta_id = ctx.id_gen.fresh(order_index, "pricing", sub_index=sub_index); sub_index += 1
            elements.append(
                BricksElement(
                    id=cta_id, name="button", parent=tier_block_id,
                    settings={
                        "text": cta["text"],
                        "link": {"type": "internal", "url": cta.get("url", "#")},
                        "style": "primary",
                    },
                )
            )
            tier_children.append(cta_id)

        elements.append(
            BricksElement(
                id=tier_block_id, name="block", parent=container_id, children=tier_children,
                settings={
                    "_padding": {"top": "32px", "right": "32px", "bottom": "32px", "left": "32px"},
                    "_border": {
                        "width": {"top": "1px", "right": "1px", "bottom": "1px", "left": "1px"},
                        "style": "solid", "color": {"raw": "var(--detail-brown)"},
                        "radius": {"top": "12px", "right": "12px", "bottom": "12px", "left": "12px"},
                    },
                },
            )
        )
        children_ids.append(tier_block_id)

    container_el = BricksElement(
        id=container_id, name="container", parent=parent_id, children=children_ids,
        settings={
            "_typography": {"text-align": "center"},
        },
    )
    return MapperResult(elements=[container_el, *elements])


# ---------- faq (accordion) ----------

def map_faq(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    items: list[dict[str, Any]] = block.get("items") or []
    if not items:
        return MapperResult(
            residual=ResidualHint(
                title=f"FAQ sin items (orden {order_index})",
                description="Bloque faq sin items extraíbles.",
                estimated_minutes=15,
            )
        )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "faq"),
        name="accordion",
        parent=parent_id,
        settings={
            "items": [
                {"title": it.get("q", ""), "content": it.get("a", ""), "open": False}
                for it in items
            ],
        },
    )
    return MapperResult(elements=[el])


# ---------- nav ----------

def map_nav(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """nav-nested es la opción Bricks 2.0+ recomendada.

    En MVP devolvemos un nav-nested con menu por defecto del WP destino;
    los items concretos (mapeados a páginas Bricks) los conecta wp-deployer.
    """
    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "nav"),
        name="nav-nested",
        parent=parent_id,
        settings={
            "menu": block.get("wp_menu_slug", "main-menu"),
            "layout": block.get("layout", "horizontal"),
            "mobile-breakpoint": "tablet_portrait",
        },
    )
    return MapperResult(elements=[el])


# ---------- footer ----------

def map_footer(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Footer es un template aparte en Bricks. Aquí emitimos una section
    para los casos en que el footer del origen está embebido en la página
    (legado Wix); wp-deployer decide si lo extrae a template global.
    """
    section, container = _section_with_container(
        order_index, parent_id, ctx,
        block_label="footer",
        bg_color="var(--bricks-color-secondary)",
    )
    container.settings["_typography"] = {"color": {"raw": "var(--bricks-color-text)"}}

    elements: list[BricksElement] = [section, container]
    columns: list[dict[str, Any]] = block.get("columns") or []
    sub_index = 2

    for col in columns:
        col_id = ctx.id_gen.fresh(order_index, "footer", sub_index=sub_index); sub_index += 1
        col_children: list[str] = []
        if (heading := col.get("heading")):
            hid = ctx.id_gen.fresh(order_index, "footer", sub_index=sub_index); sub_index += 1
            elements.append(
                BricksElement(
                    id=hid, name="heading", parent=col_id,
                    settings={"tag": "h4", "text": heading},
                )
            )
            col_children.append(hid)
        items: list[str] = col.get("items") or []
        if items:
            list_id = ctx.id_gen.fresh(order_index, "footer", sub_index=sub_index); sub_index += 1
            html_list = "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
            elements.append(
                BricksElement(
                    id=list_id, name="text", parent=col_id,
                    settings={"text": html_list},
                )
            )
            col_children.append(list_id)
        elements.append(
            BricksElement(
                id=col_id, name="block", parent=container.id, children=col_children, settings={},
            )
        )
        container.children.append(col_id)

    return MapperResult(elements=elements)


# ---------- product-card ----------

def map_product_card(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """product-card depende de WooCommerce activo. Si el proyecto no
    tiene WooCommerce, generamos tarea residual.
    """
    product_id = block.get("wp_product_id") or block.get("product_source_id")
    if product_id is None:
        return MapperResult(
            residual=ResidualHint(
                title=f"product-card sin product_id (orden {order_index})",
                description=(
                    "El content-extractor identificó una tarjeta de producto pero no se ha "
                    "asociado a un producto WooCommerce. Asegúrate de que woo-migrator se "
                    "ejecutó antes y rellenó woo_products.wp_product_id."
                ),
                estimated_minutes=15,
            )
        )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "product-card"),
        name="woocommerce-product",
        parent=parent_id,
        settings={
            "product-id": product_id,
            "display-elements": ["image", "title", "price", "add-to-cart"],
        },
    )
    return MapperResult(elements=[el])
