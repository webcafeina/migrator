"""Taxonomía semántica canónica de secciones de página + mapping a catálogo
brickstemplate (v0.29.0 B1).

El `BriefSectionAggregator` (v0.29.0) reagrupa los bloques HTML planos del
`ContentExtractor` en secciones semánticas usando estos tipos canónicos.
Cada tipo mapea 1:1 a una categoría del catálogo `brickstemplate.com` —
así `SectionPicker.get_candidates(section_type=...)` encuentra templates.

Categorías brickstemplate que NO son secciones de página (UI helpers como
button/back_to_top/popup; páginas completas como single_product/error_page;
sub-componentes como product_tabs/pros_cons) no aparecen en esta taxonomía
— el agregador no las emite.

Bug raíz fixed (WCM-053): antes del agregador, `BriefGenerator` propagaba
los `block_type` del extractor (text/heading/image/grid) como `section.type`
directos. `SectionPicker` solo matcheaba `hero` contra el catálogo → 10/1550
secciones resueltas. La taxonomía canónica reconcilia el output del LLM con
las categorías reales del catálogo.
"""

from __future__ import annotations

#: Tipos semánticos canónicos que puede emitir el BriefSectionAggregator.
#: Cada uno mapea 1:1 a una categoría del catálogo brickstemplate.
#: Verificado en `test_semantic_taxonomy.py` contra `sections-index.json`.
CANONICAL_SECTION_TYPES: tuple[str, ...] = (
    "hero",
    "features",
    "cta",
    "testimonials",
    "pricing",
    "faqs",
    "contact_form",
    "team",
    "brands",
    "products",
    "product_categories",
    "post_grid",
    "post_section",
    "counter",
    "footer",
    "slider",
)

#: Categorías brickstemplate consideradas "no sección de página". El
#: aggregator NUNCA debe emitir uno de estos como section.type.
#: - `header`: lo maneja `multilang_handler` + `nav_items_json` aparte.
#: - UI helpers: button, back_to_top, popup, pagination, cart, toc.
#: - Páginas completas: single_product, single_post, error_page, coming_soon.
#: - Sub-componentes: product_tabs, pros_cons.
#: - Solapamientos: post_loop (≈ post_grid), banner (≈ cta pequeño),
#:   bio_links/email_opt_in (variantes de cta).
NON_SECTION_CATEGORIES: frozenset[str] = frozenset({
    "header",
    "button",
    "back_to_top",
    "popup",
    "pagination",
    "cart",
    "toc",
    "single_product",
    "single_post",
    "error_page",
    "coming_soon",
    "product_tabs",
    "pros_cons",
    "post_loop",
    "bio_links",
    "banner",
    "email_opt_in",
})

#: Descripciones cortas para el system prompt del LLM. El aggregator las
#: inyecta en el prompt para que gpt-5.5 sepa cómo agrupar bloques planos
#: en cada categoría canónica.
SECTION_DESCRIPTIONS: dict[str, str] = {
    "hero": (
        "Primera sección visualmente impactante de la página: headline "
        "grande + subheadline + CTA principal + visual (imagen o "
        "background). Aparece como mucho una vez por página, al inicio."
    ),
    "features": (
        "Bloque que enumera 2-N características/servicios/beneficios con "
        "icono o número y texto corto. Layout grid o columnas. Tipo: 'Por "
        "qué elegirnos', 'Servicios', 'Cómo funciona'."
    ),
    "cta": (
        "Llamada a la acción full-width: titular + 1-2 botones. Suele ir "
        "a mitad o al final de página antes del footer. NO confundir con "
        "el CTA dentro del hero."
    ),
    "testimonials": (
        "Citas de clientes con foto + nombre + cargo. Grid de 2-N o "
        "slider. Frase entre comillas + atribución."
    ),
    "pricing": (
        "Tabla comparativa de planes/precios con lista de features por "
        "plan. Habitualmente 2-4 columnas."
    ),
    "faqs": (
        "Listado preguntas+respuestas en formato accordion o lista "
        "expandible. Pregunta corta + respuesta más larga."
    ),
    "contact_form": (
        "Formulario de contacto con campos (nombre/email/mensaje) y "
        "botón enviar."
    ),
    "team": (
        "Grid de miembros del equipo con foto + nombre + cargo + (a "
        "veces) bio corta o redes."
    ),
    "brands": (
        "Tira/grid de logos de marcas clientes o partners. Solo "
        "imágenes, sin texto descriptivo."
    ),
    "products": (
        "Grid de productos individuales (ecommerce) con imagen + título "
        "+ precio + (a veces) botón añadir."
    ),
    "product_categories": (
        "Grid de categorías de producto con imagen + nombre + (opcional) "
        "número de productos."
    ),
    "post_grid": (
        "Grid de tarjetas de blog post con thumbnail + título + excerpt "
        "+ (a veces) autor/fecha."
    ),
    "post_section": (
        "Sección de blog destacada: 1 post grande + 2-3 secundarios al "
        "lado."
    ),
    "counter": (
        "Números/estadísticas destacadas con label (ej. '100+ proyectos', "
        "'15 años de experiencia'). Tipografía grande."
    ),
    "footer": (
        "Pie de página con columnas de enlaces + datos de contacto + "
        "copyright. Aparece como mucho una vez por página al final."
    ),
    "slider": (
        "Carrusel/slider de N slides con imagen+texto navegables. "
        "Controles prev/next. NO confundir con hero estático."
    ),
}

#: Tipos de bloque HTML del ContentExtractor que el aggregator IGNORA — son
#: ruido o ya están manejados aparte (`nav`/`footer` por nav_items_json).
EXTRACTOR_NOISE_TYPES: frozenset[str] = frozenset({"unknown", "nav"})


def canonical_for_extractor_type(extractor_type: str) -> str | None:
    """Fast-path: mapping directo extractor.block_type → semantic_type.

    Para los `block_type` que YA son semánticamente claros (`hero`, `cta`,
    `pricing`, `faq`, `form`, `testimonial`, `slider`), saltarse el LLM
    y asignar directamente. Reduce coste del agregador para páginas
    cuyo extractor ya tipó bien (~10-30% según corpus mariya.design).

    Devuelve None si no hay un mapping obvio — el LLM decidirá tras
    examinar el contexto.
    """
    direct: dict[str, str | None] = {
        "hero": "hero",
        "cta": "cta",
        "pricing": "pricing",
        "faq": "faqs",
        "form": "contact_form",
        "testimonial": "testimonials",
        "slider": "slider",
        # Ambiguos: el LLM decide
        "gallery": None,
        "grid": None,
        "text": None,
        "heading": None,
        "image": None,
        "accordion": None,
        "tabs": None,
    }
    return direct.get(extractor_type)


def is_canonical_type(t: str) -> bool:
    """True si `t` es un tipo emitible por el aggregator."""
    return t in CANONICAL_SECTION_TYPES
