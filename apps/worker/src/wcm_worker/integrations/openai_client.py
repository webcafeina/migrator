"""OpenAIClient — wrapper async sobre OpenAI SDK con function calling.

Sprint v0.25.0. Sustituye al desactivado `ClaudeVisionClient` como cliente
LLM productivo del worker. Anthropic queda fuera del scope (créditos free
agotados; sin tier pagado). OpenAI sí (operador ya paga su API).

Casos de uso:

1. **`generate_brief_metadata(scraping_summary, theme_hints, fingerprint)`**
   — modelo `gpt-4o-mini` (barato, ~$0.01/proyecto). Devuelve dict con
   business_description + sector + tone_of_voice + target_audience + usps[].
   Usado por `BriefGeneratorAgent` cuando los campos no están seteados por
   el operador en el wizard.

2. **`generate_page_redesign(brief, page_spec)`** — modelo `gpt-4o` (calidad,
   ~$0.30-1.50/página). Devuelve un page content Bricks (array de elementos
   válidos contra `BRICKS_ELEMENT_NAMES`). Usado por `RedesignAIAgent`.

Diseño:
- API call vía `client.chat.completions.create()` con `tools=[...]` +
  `tool_choice={"type":"function","function":{"name":"..."}}` para forzar
  la respuesta estructurada.
- Validación de output contra JSON Schema antes de devolverlo.
- Retry exponencial + detección 429 con pausa larga.
- Cost tracking (tokens × pricing) — registrar fuera (no en BD desde aquí).

Pricing (a 2026-05-28, datos públicos OpenAI):
- `gpt-4o-mini`: $0.15/MTok input, $0.60/MTok output
- `gpt-4o`: $2.50/MTok input, $10/MTok output
- `gpt-5`: $1.25/MTok input, $10/MTok output (v0.27.0 default redesign)
- `gpt-5-mini`: $0.25/MTok input, $2/MTok output (estimación; cheaper alt)

Nota: en v0.26.0 se asumió `gpt-5.5` por WebSearch, pero ese SKU no existe
en OpenAI (alucinación del search). Los SKUs reales gpt-5 family son
`gpt-5`, `gpt-5-mini`, `gpt-5-chat-latest`. Corregido v0.27.0.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from typing import Any

from wcm_worker.errors import (
    OpenAIAuthError,
    OpenAIClientError,
    OpenAIInvalidOutputError,
    OpenAIRateLimitError,
)

log = logging.getLogger("wcm.worker.openai_client")

#: Modelos por defecto.
DEFAULT_MODEL_METADATA = "gpt-4o-mini"
#: v0.27.0 — default real `gpt-5` (no `gpt-5.5` que no existe).
#: Override con env OPENAI_MODEL_REDESIGN.
DEFAULT_MODEL_REDESIGN = "gpt-5"
#: v0.26.0 — modelo de generación de imágenes (gpt-image-2 abril 2026).
DEFAULT_MODEL_IMAGE = "gpt-image-2"

# v0.27.0 — gpt-5 family es reasoning model (thinking interno antes
# de responder). 90s era suficiente para gpt-4o pero gpt-5 puede
# tardar 2-4 min en respuestas estructuradas con tool_use forzado.
DEFAULT_TIMEOUT_S = 300.0
DEFAULT_RETRIES = 5
#: Pausa tras 429 — tier free OpenAI suele exigir 60s mínimo.
DEFAULT_RATE_LIMIT_PAUSE_S = 60.0

#: v0.26.0 — pricing fijo por imagen gpt-image-2 según quality + size.
#: Fuente: OpenAI API docs (abril 2026).
IMAGE_PRICING_USD: dict[tuple[str, str], float] = {
    ("low", "1024x1024"): 0.006,
    ("medium", "1024x1024"): 0.053,
    ("high", "1024x1024"): 0.211,
    ("low", "1024x1536"): 0.005,
    ("medium", "1024x1536"): 0.041,
    ("high", "1024x1536"): 0.165,
    ("low", "1536x1024"): 0.005,
    ("medium", "1536x1024"): 0.041,
    ("high", "1536x1024"): 0.165,
}

#: Pricing por millón de tokens (USD). Si OpenAI cambia precios, actualizar.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    # v0.27.0 — gpt-5 family (verificado contra /v1/models 2026-05-28).
    "gpt-5": (1.25, 10.0),
    "gpt-5-mini": (0.25, 2.0),
    "gpt-5-chat-latest": (1.25, 10.0),
    # backups en caso de rotación a otros modelos:
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-3.5-turbo": (0.50, 1.50),
}


@dataclass
class OpenAIResult:
    """Resultado canónico de cualquier call al cliente.

    `data` es el dict ya parseado del function call (no JSON crudo).
    `tokens_in`/`tokens_out` para cost tracking en BD.
    """

    data: dict[str, Any]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str


@dataclass
class OpenAIImageResult:
    """v0.26.0 — resultado de generate_image (gpt-image-2).

    `image_bytes` es el PNG/WEBP crudo que subimos a R2.
    `cost_usd` se calcula desde IMAGE_PRICING_USD (no token-based).
    """

    image_bytes: bytes
    mime: str
    width: int
    height: int
    cost_usd: float
    model: str
    quality: str
    size: str
    prompt: str


# ---------- prompts ----------

#: BriefGenerator — `gpt-4o-mini`. Input compacto, output estructurado.
SYSTEM_PROMPT_BRIEF_METADATA = """Eres un consultor de branding y marketing web. \
Tu tarea: dado el contenido scrapeado de una web origen (textos, headings, \
páginas detectadas, paleta de colores), inferir 5 metadatos del negocio:

1. **business_description** (2-4 frases, español de España): qué hace la empresa, \
qué servicios/productos ofrece, qué la diferencia.
2. **business_sector** (1 palabra inglesa): uno de los slugs canónicos: \
restaurant, agency, consulting, services, ecommerce, portfolio, fitness, \
hotel, healthcare, legal, education, realestate, beauty, automotive, other.
3. **tone_of_voice**: uno de formal | casual | friendly | premium | playful | serious.
4. **target_audience** (1-2 frases): a quién se dirige el negocio principalmente.
5. **usps**: lista de 3 a 5 strings cortos (≤6 palabras cada uno) con los \
unique selling points o ventajas que el sitio comunica explícitamente.

Reglas:
- Sé conservador. Si la web NO dice algo claramente, NO lo inventes — usa frases \
genéricas adecuadas al sector.
- target_audience: cuando solo haya pistas débiles, asume "público general del sector".
- USPs solo extrapolas de copy real del sitio.
- Devuelve SIEMPRE la tool `emit_brief_metadata` con los 5 campos.
"""

#: Schema de la tool `emit_brief_metadata` para BriefGenerator.
TOOL_BRIEF_METADATA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_brief_metadata",
        "description": (
            "Emite los 5 metadatos del Brief canónico del negocio "
            "deducidos del scraping del origen."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "business_description": {
                    "type": "string",
                    "minLength": 30,
                    "maxLength": 1500,
                },
                "business_sector": {
                    "type": "string",
                    "enum": [
                        "restaurant", "agency", "consulting", "services",
                        "ecommerce", "portfolio", "fitness", "hotel",
                        "healthcare", "legal", "education", "realestate",
                        "beauty", "automotive", "other",
                    ],
                },
                "tone_of_voice": {
                    "type": "string",
                    "enum": ["formal", "casual", "friendly", "premium", "playful", "serious"],
                },
                "target_audience": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 500,
                },
                "usps": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 80,
                    },
                },
            },
            "required": [
                "business_description", "business_sector",
                "tone_of_voice", "target_audience", "usps",
            ],
            "additionalProperties": False,
        },
    },
}


#: RedesignAI — `gpt-4o`. Construye páginas Bricks completas desde el Brief.
SYSTEM_PROMPT_PAGE_REDESIGN = """Eres un experto diseñador web especializado en \
WordPress + Bricks Builder. Tu objetivo: dado un Brief de negocio y la spec de \
una página, generar un array de elementos Bricks NATIVOS (flat tree con parent/children \
por ID) que represente una página moderna, limpia y bien estructurada.

Reglas estrictas:
1. **Elementos permitidos** (catálogo MVP): section, container, block, div, \
heading, text, text-basic, text-link, image, image-gallery, button, icon, \
icon-box, divider, spacer, slider-nested, tabs-nested, accordion, accordion-nested, \
nav-menu, nav-nested, form, shortcode, code. Otros nombres serán rechazados.
2. **Estructura plana con relaciones por ID**: el primer elemento DEBE ser \
una `section` con `parent: "0"`. Todos los demás referencian un parent existente. \
`children` es lista de IDs (no objetos anidados).
3. **IDs únicos** de 6 caracteres alfanuméricos minúsculas (`[a-z0-9]{6}`).
4. **Color SIEMPRE como `{"raw": "..."}`**: ej `{"color": {"raw": "var(--bricks-color-primary)"}}`. \
String pelado es descartado por Bricks.
5. **Tokens del Brief**: usa `var(--bricks-color-primary|secondary|accent|text|bg)` \
para los colores; fonts del `brand.fonts` (Inter, Playfair Display, etc.).
6. **Padding/border como object**: `_padding: {top, right, bottom, left}` con \
unidades CSS (px, rem). NO numbers pelados.
7. **Responsive opcional**: usa sufijo `:tablet_portrait` o `:mobile_portrait` \
en las keys cuando cambies grid/padding por breakpoint.
8. **Contenido del Brief**: úsalo literal cuando esté presente (headlines, USPs, \
description). NO inventes copy ajeno al brief.
9. **Diseño limpio y moderno**: pocas secciones, jerarquía clara, espaciado \
generoso, paleta del brand. Sin position absolute, sin overlays raros.

Devuelve SIEMPRE la tool `emit_bricks_page` con el array `content`.
"""

#: Schema de la tool `emit_bricks_page` para RedesignAI.
#: Catálogo de elementos permitidos centralizado y enum-validado.
_ALLOWED_ELEMENT_NAMES = [
    "section", "container", "block", "div",
    "heading", "text", "text-basic", "text-link",
    "image", "image-gallery", "video", "icon", "icon-box",
    "button", "accordion", "accordion-nested",
    "slider-nested", "tabs-nested",
    "nav-menu", "nav-nested", "form", "shortcode",
    "divider", "spacer", "code",
]

#: RedesignAI v0.26.0 — generación SECCIÓN por sección (modo Hybrid).
#: Solo emite UNA section subtree (la sección + sus descendientes).
#: La página se compone agregando subtrees.
SYSTEM_PROMPT_SECTION_REDESIGN = """Eres un experto diseñador web especializado en \
WordPress + Bricks Builder. Tu objetivo: dado un Brief de negocio y la spec de \
UNA SECCIÓN concreta dentro de una página, generar un subárbol Bricks NATIVO \
(flat tree con parent/children por ID) que represente esa sección sola, lista \
para encajar en una página más grande.

Reglas estrictas (idénticas a generación de página, pero scope sección):
1. **Elementos permitidos**: section, container, block, div, heading, text, \
text-basic, text-link, image, image-gallery, button, icon, icon-box, divider, \
spacer, slider-nested, tabs-nested, accordion, accordion-nested, nav-menu, \
nav-nested, form, shortcode, code.
2. **El primer elemento DEBE ser una `section` con `parent: "0"`**. Los demás \
referencian un parent existente del propio subtree.
3. **IDs únicos** de 6 caracteres alfanuméricos minúsculas (`[a-z0-9]{6}`). \
DEBEN ser únicos en el ámbito del subtree (no colisionar con otras secciones — \
usa IDs aleatorios que no parezcan secuenciales).
4. **Color SIEMPRE como `{"raw": "..."}`**. Tokens del brand: \
`var(--bricks-color-primary|secondary|accent|text|bg)`.
5. **Padding/border como object**: `_padding: {top, right, bottom, left}` con \
unidades CSS.
6. **Responsive opcional**: sufijo `:tablet_portrait` / `:mobile_portrait`.
7. **Contenido del Brief**: úsalo literal cuando esté presente.
8. **Una sola section root**: no múltiples top-level. Si la sección original \
es compleja (hero con CTA), todo va dentro de la misma section root.

Devuelve SIEMPRE la tool `emit_bricks_section` con el array `content`.
"""

#: Schema de la tool `emit_bricks_section`. Comparte allowed_names con la
#: tool de página entera para que el resto del pipeline (validador, mappers)
#: trate ambos outputs igual.
TOOL_SECTION_REDESIGN: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_bricks_section",
        "description": (
            "Emite el array `content` del subárbol Bricks de UNA sección. "
            "El primer elemento DEBE ser una `section` con parent='0'. "
            "Los demás son sus descendientes (parent ID dentro del subtree)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "pattern": "^[a-z0-9]{6}$",
                            },
                            "name": {
                                "type": "string",
                                "enum": _ALLOWED_ELEMENT_NAMES,
                            },
                            "parent": {"type": "string"},
                            "children": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "settings": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["id", "name", "parent", "settings"],
                        "additionalProperties": False,
                    },
                },
                "notes": {
                    "type": "string",
                    "description": "Comentarios libres del modelo.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
}


TOOL_PAGE_REDESIGN: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_bricks_page",
        "description": (
            "Emite el array `content` de la página Bricks con estructura "
            "plana parent/children. Cada elemento tiene id (6 chars), "
            "name, parent ('0' para top-level section), children (lista de IDs), "
            "y settings (dict con _typography, _padding, _background, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "pattern": "^[a-z0-9]{6}$",
                            },
                            "name": {
                                "type": "string",
                                "enum": _ALLOWED_ELEMENT_NAMES,
                            },
                            "parent": {"type": "string"},
                            "children": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "settings": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["id", "name", "parent", "settings"],
                        "additionalProperties": False,
                    },
                },
                "notes": {
                    "type": "string",
                    "description": "Comentarios libres sobre decisiones de diseño tomadas.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
}


#: BriefRefinement v0.27.0 — analiza Brief + páginas Bricks ya generadas
#: y propone mejoras concretas en 4 categorías editables.
SYSTEM_PROMPT_BRIEF_REFINEMENT = """Eres un consultor senior de UX writing y \
conversión web. Tu tarea: dado un Brief de negocio y un resumen de las páginas \
Bricks generadas, proponer **5 a 15 mejoras concretas** en una de estas 4 \
categorías:

1. **copy**: mejorar headlines, subheadlines, descriptions o cualquier texto \
literal del Brief. Más enganchador, más beneficio-orientado, más concreto.
2. **cta**: mejorar el texto del CTA (`cta_text`) y/o su URL destino (`cta_url`) \
para aumentar clarity y conversión.
3. **design_method**: cambiar el método de generación de una sección entre \
`templates` (estable, determinista) y `ai` (creativo, más caro). Por ejemplo, \
si el hero quedó plano con templates, sugerir cambiar a `ai`.
4. **reorder**: cambiar el orden de las secciones dentro de una página para \
mejorar el flujo narrativo (hero → problema → solución → social proof → CTA).

Reglas:
- **NO propongas añadir o eliminar secciones** (fuera de scope v0.27.0).
- Cada propuesta debe ser **accionable y atómica**.
- `before` y `after` deben ser **válidos según category**:
  - `copy`: `{"key": "headline|subheadline|description|text", "value": "string"}`.
  - `cta`: `{"cta_text": "string", "cta_url": "string"}`. Permites omitir uno.
  - `design_method`: `{"design_method": "templates|ai"}`.
  - `reorder`: `{"new_order": [int]}` (lista de índices originales en nuevo orden).
- `rationale` máx 200 caracteres, en español de España, sin jerga.
- `impact_estimate`: low/medium/high según relevancia comercial.
- Idioma de copy generado: SIEMPRE español de España.

Devuelve SIEMPRE la tool `emit_brief_refinements` con `proposals`.
"""

TOOL_BRIEF_REFINEMENT: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_brief_refinements",
        "description": (
            "Emite una lista de 5-15 propuestas de mejora del Brief en 4 "
            "categorías: copy, cta, design_method, reorder. Cada propuesta "
            "tiene before/after, rationale y impact_estimate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "proposals": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 30,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": (
                                    "UUID v4 corto generado por el modelo "
                                    "para identificar la propuesta."
                                ),
                            },
                            "category": {
                                "type": "string",
                                "enum": [
                                    "copy", "cta", "design_method", "reorder",
                                ],
                            },
                            "page_slug": {"type": "string"},
                            "section_index": {
                                "type": "integer",
                                "minimum": 0,
                                "description": (
                                    "Índice 0-based en page.sections[]. "
                                    "Para `reorder`, índice de la página "
                                    "(la reordenación es a nivel página)."
                                ),
                            },
                            "before": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                            "after": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                            "rationale": {
                                "type": "string",
                                "maxLength": 240,
                            },
                            "impact_estimate": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                        },
                        "required": [
                            "id", "category", "page_slug", "section_index",
                            "before", "after", "rationale", "impact_estimate",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["proposals"],
            "additionalProperties": False,
        },
    },
}


class OpenAIClient:
    """Cliente async para function calling estructurado.

    Lazy import del SDK `openai` para que el módulo cargue aunque la
    dep no esté instalada (tests con mock no la necesitan).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model_metadata: str = DEFAULT_MODEL_METADATA,
        model_redesign: str = DEFAULT_MODEL_REDESIGN,
        model_image: str = DEFAULT_MODEL_IMAGE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.model_image = model_image
        if not api_key:
            raise OpenAIAuthError("OPENAI_API_KEY vacío")
        self.api_key = api_key
        self.model_metadata = model_metadata
        self.model_redesign = model_redesign
        self.timeout_s = timeout_s
        self.retries = retries
        # max_retries=0 — gestionamos retries nosotros (cap+jitter+rate-limit).
        from openai import AsyncOpenAI  # noqa: PLC0415 — lazy
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_s,
            max_retries=0,
        )

    @classmethod
    def from_env(cls) -> OpenAIClient | None:
        """Construye desde env vars. Devuelve None si `OPENAI_API_KEY` falta."""
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            return None
        return cls(
            api_key=key,
            model_metadata=os.environ.get("OPENAI_MODEL_METADATA", DEFAULT_MODEL_METADATA),
            model_redesign=os.environ.get("OPENAI_MODEL_REDESIGN", DEFAULT_MODEL_REDESIGN),
            model_image=os.environ.get("OPENAI_MODEL_IMAGE", DEFAULT_MODEL_IMAGE),
        )

    # ---------- public ----------

    async def generate_brief_metadata(
        self,
        *,
        scraping_summary: str,
        theme_hints: dict[str, Any] | None = None,
        fingerprint: dict[str, Any] | None = None,
    ) -> OpenAIResult:
        """Genera business_description + sector + tone + target + usps.

        Usado por BriefGenerator cuando los campos no están seteados.
        Modelo: `model_metadata` (default gpt-4o-mini).
        """
        user_msg = self._build_brief_metadata_user_message(
            scraping_summary=scraping_summary,
            theme_hints=theme_hints or {},
            fingerprint=fingerprint or {},
        )
        return await self._call_with_retry(
            model=self.model_metadata,
            system=SYSTEM_PROMPT_BRIEF_METADATA,
            user_msg=user_msg,
            tool=TOOL_BRIEF_METADATA,
            tool_name="emit_brief_metadata",
        )

    async def generate_page_redesign(
        self,
        *,
        brief: dict[str, Any],
        page_spec: dict[str, Any],
    ) -> OpenAIResult:
        """Genera el array Bricks de UNA página a partir del Brief + spec.

        Modelo: `model_redesign` (default gpt-4o, v0.26.0 default gpt-5.5).
        Más caro pero mejor calidad estructural.
        """
        user_msg = self._build_page_redesign_user_message(brief, page_spec)
        return await self._call_with_retry(
            model=self.model_redesign,
            system=SYSTEM_PROMPT_PAGE_REDESIGN,
            user_msg=user_msg,
            tool=TOOL_PAGE_REDESIGN,
            tool_name="emit_bricks_page",
        )

    async def generate_section_redesign(
        self,
        *,
        brief: dict[str, Any],
        page_spec: dict[str, Any],
        section_spec: dict[str, Any],
    ) -> OpenAIResult:
        """v0.26.0 — genera subárbol Bricks de UNA sección concreta.

        Usado por `RedesignAIAgent` en modo Hybrid (cuando
        `Project.design_method is None`) para procesar solo las secciones
        marcadas como `design_method == "ai"`. La página se compone
        ensamblando subtrees + las secciones generadas por templates.

        Coste estimado por sección con gpt-5.5: $0.05-0.30 (vs
        $0.30-1.50 por página entera con gpt-4o).
        """
        user_msg = self._build_section_redesign_user_message(
            brief, page_spec, section_spec
        )
        return await self._call_with_retry(
            model=self.model_redesign,
            system=SYSTEM_PROMPT_SECTION_REDESIGN,
            user_msg=user_msg,
            tool=TOOL_SECTION_REDESIGN,
            tool_name="emit_bricks_section",
        )

    async def generate_brief_refinement(
        self,
        *,
        brief: dict[str, Any],
        pages_summary: list[dict[str, Any]],
    ) -> OpenAIResult:
        """v0.27.0 — propone mejoras al Brief en 4 categorías.

        `pages_summary` es un resumen COMPACTO (sin bricks_json crudo)
        de cada página: `{slug, intent, sections: [{type, design_method,
        headline, has_image}]}`. Mantiene el prompt corto y barato.

        Modelo: `model_redesign` (default gpt-5.5). Coste estimado por
        proyecto típico (Brief + 5 páginas + 20 secciones): $0.10-0.50.
        """
        user_msg = self._build_brief_refinement_user_message(
            brief, pages_summary,
        )
        return await self._call_with_retry(
            model=self.model_redesign,
            system=SYSTEM_PROMPT_BRIEF_REFINEMENT,
            user_msg=user_msg,
            tool=TOOL_BRIEF_REFINEMENT,
            tool_name="emit_brief_refinements",
        )

    async def generate_image(
        self,
        *,
        prompt: str,
        quality: str = "medium",
        size: str = "1024x1024",
        n: int = 1,
    ) -> OpenAIImageResult:
        """v0.26.0 — genera imagen con gpt-image-2.

        Coste fijo por imagen según (quality, size) en IMAGE_PRICING_USD.
        Devuelve los bytes PNG/WEBP listos para subir a R2.

        - `quality`: low / medium / high. Default medium (~$0.05/imagen
          a 1024x1024). High calidad cuesta ~4x más.
        - `size`: "1024x1024" (cuadrado, decorativo) /
          "1024x1536" (vertical) / "1536x1024" (horizontal, hero).
        - `n`: número de imágenes a generar (cada una factura aparte).
        """
        if (quality, size) not in IMAGE_PRICING_USD:
            raise OpenAIClientError(
                f"Combinación inválida quality={quality!r} size={size!r}. "
                f"Disponibles: {list(IMAGE_PRICING_USD.keys())[:3]}..."
            )
        try:
            response = await self._client.images.generate(
                model=self.model_image,
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                raise OpenAIRateLimitError(str(e)) from e
            if "auth" in msg or "401" in msg or "invalid api" in msg:
                raise OpenAIAuthError(str(e)) from e
            raise OpenAIClientError(f"image generation failed: {e}") from e

        # OpenAI SDK images.generate devuelve data: [{b64_json | url}]. En el
        # último release b64_json viene por defecto cuando no se pide URL.
        if not response.data:
            raise OpenAIInvalidOutputError("image generation: response.data vacío")
        first = response.data[0]
        b64 = getattr(first, "b64_json", None)
        if not b64:
            raise OpenAIInvalidOutputError("image generation: sin b64_json en respuesta")
        import base64  # noqa: PLC0415 — lazy
        image_bytes = base64.b64decode(b64)
        w, h = (int(p) for p in size.split("x"))
        return OpenAIImageResult(
            image_bytes=image_bytes,
            mime="image/png",
            width=w,
            height=h,
            cost_usd=IMAGE_PRICING_USD[(quality, size)] * n,
            model=self.model_image,
            quality=quality,
            size=size,
            prompt=prompt,
        )

    # ---------- internals ----------

    async def _call_with_retry(
        self,
        *,
        model: str,
        system: str,
        user_msg: str,
        tool: dict[str, Any],
        tool_name: str,
    ) -> OpenAIResult:
        """Retry exponencial con jitter + detección 429 con pausa larga."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                return await self._call_once(
                    model=model, system=system,
                    user_msg=user_msg, tool=tool, tool_name=tool_name,
                )
            except OpenAIAuthError:
                raise  # 401/403 no retriable
            except OpenAIInvalidOutputError as e:
                last_error = e
                raise  # invalid output → caller decide fallback
            except OpenAIRateLimitError as e:
                last_error = e
                if attempt == self.retries - 1:
                    raise
                wait = DEFAULT_RATE_LIMIT_PAUSE_S + random.uniform(0, 5)
                log.warning(
                    "openai_retry_rate_limit",
                    extra={"attempt": attempt + 1, "wait_s": wait, "error": str(e)[:120]},
                )
                await asyncio.sleep(wait)
            except OpenAIClientError as e:
                last_error = e
                if attempt == self.retries - 1:
                    raise
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                log.warning(
                    "openai_retry",
                    extra={"attempt": attempt + 1, "wait_s": wait, "error": str(e)[:120]},
                )
                await asyncio.sleep(wait)
        raise OpenAIClientError(f"Failed after {self.retries} retries: {last_error}")

    async def _call_once(
        self,
        *,
        model: str,
        system: str,
        user_msg: str,
        tool: dict[str, Any],
        tool_name: str,
    ) -> OpenAIResult:
        """Una sola llamada a chat.completions.create con tool forzado.

        v0.27.0 — gpt-5 family rechaza `temperature` con valor != 1
        (HTTP 400 unsupported_value). Solo enviamos el parámetro para
        modelos gpt-4* donde sí es relevante.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "tools": [tool],
            "tool_choice": {
                "type": "function",
                "function": {"name": tool_name},
            },
        }
        # gpt-5 family solo admite temperature=1 (el default). Para
        # gpt-4 family pedimos 0.7 que mejora variabilidad estructural.
        if not model.startswith("gpt-5"):
            kwargs["temperature"] = 0.7
        else:
            # v0.27.0 — gpt-5 family acepta `reasoning_effort`. Default
            # es `high` (thinking eterno: 5-18 min por página). Para tareas
            # estructuradas con tool_use forzado `low` es suficiente:
            # baja latencia a 30-90s sin sacrificar la calidad estructural
            # (la decisión de estructura se hace en el system prompt + tool
            # schema, no en el reasoning).
            kwargs["reasoning_effort"] = "low"
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001 — SDK raises various subtypes
            msg = str(e).lower()
            if "401" in msg or "403" in msg or "invalid api key" in msg or "authentication" in msg:
                raise OpenAIAuthError(f"Auth failed: {e}") from e
            if "429" in msg or "rate" in msg or "too many" in msg:
                raise OpenAIRateLimitError(f"Rate limited: {e}") from e
            raise OpenAIClientError(f"API call failed: {e}") from e

        # Parse tool call
        choice = response.choices[0]
        if not choice.message.tool_calls or len(choice.message.tool_calls) == 0:
            raise OpenAIInvalidOutputError(
                "El modelo no invocó la tool obligatoria"
            )
        tc = choice.message.tool_calls[0]
        if tc.function.name != tool_name:
            raise OpenAIInvalidOutputError(
                f"Tool inesperada: {tc.function.name} (esperaba {tool_name})"
            )
        try:
            data = json.loads(tc.function.arguments)
        except json.JSONDecodeError as e:
            raise OpenAIInvalidOutputError(
                f"Arguments no es JSON válido: {e}"
            ) from e

        # Cost tracking
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0
        cost = _estimate_cost(model, tokens_in, tokens_out)

        return OpenAIResult(
            data=data,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            model=model,
        )

    @staticmethod
    def _build_brief_metadata_user_message(
        *,
        scraping_summary: str,
        theme_hints: dict[str, Any],
        fingerprint: dict[str, Any],
    ) -> str:
        """Construye user message compacto para BriefMetadata.

        Cap del scraping_summary a 8KB para evitar quemar tokens en
        webs largas. Las decisiones de qué resumir las toma el caller.
        """
        max_summary = 8 * 1024
        if len(scraping_summary) > max_summary:
            scraping_summary = scraping_summary[:max_summary] + "\n<!-- TRUNCATED -->"

        parts = [
            "## Contenido scrapeado de la web origen",
            scraping_summary,
        ]
        if theme_hints:
            parts.extend([
                "",
                "## Pistas de paleta y tipografía detectadas",
                json.dumps(theme_hints, ensure_ascii=False, indent=2)[:1500],
            ])
        if fingerprint:
            parts.extend([
                "",
                "## Fingerprint adicional (builder, región, sector pre-inferido)",
                json.dumps(fingerprint, ensure_ascii=False, indent=2)[:500],
            ])
        return "\n".join(parts)

    @staticmethod
    def _build_page_redesign_user_message(
        brief: dict[str, Any], page_spec: dict[str, Any]
    ) -> str:
        """Construye user message para RedesignAI por página."""
        parts = [
            "## Brief del negocio",
            json.dumps(brief.get("business", {}), ensure_ascii=False, indent=2),
            "",
            "## Branding (paleta, fuentes, voz)",
            json.dumps(brief.get("brand", {}), ensure_ascii=False, indent=2),
            "",
            "## Spec de la página a generar",
            json.dumps(page_spec, ensure_ascii=False, indent=2),
            "",
            "Genera el array `content` de elementos Bricks NATIVOS para esta página.",
            "Usa colores del brand como `var(--bricks-color-*)` y fonts del brand.",
            "Estructura limpia, jerarquía clara, espaciado generoso. Mobile-first.",
        ]
        return "\n".join(parts)

    @staticmethod
    def _build_brief_refinement_user_message(
        brief: dict[str, Any],
        pages_summary: list[dict[str, Any]],
    ) -> str:
        """v0.27.0 — user message para BriefRefinement.

        Estructura: Brief business + brand + páginas resumidas.
        """
        parts = [
            "## Brief del negocio",
            json.dumps(brief.get("business", {}), ensure_ascii=False, indent=2),
            "",
            "## Branding",
            json.dumps(brief.get("brand", {}), ensure_ascii=False, indent=2),
            "",
            "## Resumen de páginas Bricks ya generadas",
            json.dumps(pages_summary, ensure_ascii=False, indent=2),
            "",
            "Propón 5-15 mejoras concretas en categorías copy/cta/design_method/reorder.",
            "Sé específico: cita el page_slug + section_index exactos.",
            "NO propongas añadir o eliminar secciones (fuera de scope).",
        ]
        return "\n".join(parts)

    @staticmethod
    def _build_section_redesign_user_message(
        brief: dict[str, Any],
        page_spec: dict[str, Any],
        section_spec: dict[str, Any],
    ) -> str:
        """v0.26.0 — user message para RedesignAI por sección.

        Contexto reducido: solo business + brand + intent de la página +
        spec de la sección. El modelo no necesita ver el resto de
        secciones porque no las genera.
        """
        page_meta = {
            "slug": page_spec.get("slug"),
            "title": page_spec.get("title"),
            "intent": page_spec.get("intent"),
        }
        parts = [
            "## Brief del negocio",
            json.dumps(brief.get("business", {}), ensure_ascii=False, indent=2),
            "",
            "## Branding (paleta, fuentes, voz)",
            json.dumps(brief.get("brand", {}), ensure_ascii=False, indent=2),
            "",
            "## Página contenedora (para tono/intent)",
            json.dumps(page_meta, ensure_ascii=False, indent=2),
            "",
            "## Spec de la sección a generar",
            json.dumps(section_spec, ensure_ascii=False, indent=2),
            "",
            "Genera el array `content` con UN subárbol Bricks NATIVO para esta sección.",
            "El primer elemento DEBE ser una `section` con `parent: \"0\"`.",
            "Usa colores del brand como `var(--bricks-color-*)` y fonts del brand.",
            "Diseño limpio, jerarquía clara, espaciado generoso, mobile-first.",
        ]
        return "\n".join(parts)


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Devuelve coste USD estimado. 0.0 si modelo desconocido."""
    pricing = PRICING_USD_PER_MTOK.get(model)
    if pricing is None:
        return 0.0
    input_rate, output_rate = pricing
    return (tokens_in * input_rate + tokens_out * output_rate) / 1_000_000


def make_client_from_env() -> OpenAIClient | None:
    """Factory helper. Conveniente para agentes que necesitan check rápido."""
    return OpenAIClient.from_env()


__all__ = [
    "OpenAIClient",
    "OpenAIResult",
    "OpenAIImageResult",
    "PRICING_USD_PER_MTOK",
    "IMAGE_PRICING_USD",
    "DEFAULT_MODEL_METADATA",
    "DEFAULT_MODEL_REDESIGN",
    "DEFAULT_MODEL_IMAGE",
    "make_client_from_env",
    "_estimate_cost",
]
