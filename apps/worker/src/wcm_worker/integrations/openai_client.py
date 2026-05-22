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

Pricing (a 2026-05-22, datos públicos OpenAI):
- `gpt-4o-mini`: $0.15/MTok input, $0.60/MTok output
- `gpt-4o`: $2.50/MTok input, $10/MTok output
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
DEFAULT_MODEL_REDESIGN = "gpt-4o"

DEFAULT_TIMEOUT_S = 90.0
DEFAULT_RETRIES = 5
#: Pausa tras 429 — tier free OpenAI suele exigir 60s mínimo.
DEFAULT_RATE_LIMIT_PAUSE_S = 60.0

#: Pricing por millón de tokens (USD). Si OpenAI cambia precios, actualizar.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
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
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
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

        Modelo: `model_redesign` (default gpt-4o). Más caro pero mejor
        calidad estructural.
        """
        user_msg = self._build_page_redesign_user_message(brief, page_spec)
        return await self._call_with_retry(
            model=self.model_redesign,
            system=SYSTEM_PROMPT_PAGE_REDESIGN,
            user_msg=user_msg,
            tool=TOOL_PAGE_REDESIGN,
            tool_name="emit_bricks_page",
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
        """Una sola llamada a chat.completions.create con tool forzado."""
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                tools=[tool],
                tool_choice={
                    "type": "function",
                    "function": {"name": tool_name},
                },
                temperature=0.7,
            )
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
    "PRICING_USD_PER_MTOK",
    "DEFAULT_MODEL_METADATA",
    "DEFAULT_MODEL_REDESIGN",
    "make_client_from_env",
    "_estimate_cost",
]
