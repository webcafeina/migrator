"""ClaudeVisionClient — wrapper async sobre Anthropic SDK con vision + tool_use.

Sprint v0.22.0 (AI.2). Pieza central del bloque AI: dado un screenshot
PNG de una sección + HTML estructural + computed styles, devuelve una
lista de elementos Bricks NATIVOS (heading, text, image, button,
container) que reproducen el aspecto del origen lo más fielmente
posible.

Diseño:
- API call con `client.messages.create()` que envía:
  - System prompt con el catálogo Bricks + reglas de generación.
  - User message multimodal: imagen (screenshot) + texto (HTML + selector).
  - Tool definition `emit_bricks_elements` con JSON Schema riguroso del
    output esperado.
- Forzamos `tool_choice={"type": "tool", "name": "emit_bricks_elements"}`
  para que Claude SIEMPRE invoque la tool — sin esto puede responder
  texto libre que es inutilizable.
- Cache en BD `ai_section_cache` por sha256(png + html + selector).
  Reutilizable cross-project (mariya.design dos veces → mismo cache).
- Retry exponencial con jitter en errores 5xx/429.
- Tracking de tokens y coste por call (alimenta el budget cap del
  `AiAssistAgent`).

Pricing modelo claude-sonnet-4-6 (a 2026-05-21):
- $3/MTok input, $15/MTok output
- Imagen ~1500 tokens, prompt ~1500 tokens, output ~500 tokens
- ≈ $0.012 input + $0.0075 output = ~$0.02 por sección
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Any

from wcm_worker.errors import (
    ClaudeVisionApiError,
    ClaudeVisionAuthError,
    ClaudeVisionInvalidOutputError,
)

log = logging.getLogger("wcm.worker.claude_vision")

#: Modelo por defecto. Sonnet 4.6 (con vision) tiene buen balance
#: calidad/coste para análisis de layouts.
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_RETRIES = 3

#: Pricing por millón de tokens (USD). Se usa para registrar `cost_usd`
#: en la tabla `ai_section_cache`. Si rotamos modelo, actualizar aquí.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # input, output
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
}


#: System prompt — descripción del catálogo Bricks que Claude debe
#: usar. Mantener corto: cada token cuesta. El listado completo de
#: settings va en la tool definition (JSON Schema).
SYSTEM_PROMPT = """Eres un experto en reproducir layouts web como JSON de Bricks Builder \
(WordPress). Tu objetivo: dado un screenshot + HTML de una sección, emitir un \
array de elementos Bricks NATIVOS que reproduzcan el aspecto lo más fielmente \
posible, manteniendo el contenido editable en el editor visual de Bricks.

Reglas estrictas:
1. **Elementos permitidos**: section, container, block, div, heading, text, \
text-basic, image, button, icon, divider, spacer, slider-nested, nav-nested, \
form, shortcode, code. Cualquier otro nombre será rechazado.
2. **Estructura obligatoria**: el primer elemento DEBE ser una `section` con \
`parent="0"`, conteniendo un `container` con los demás children.
3. **IDs**: cada elemento lleva un `id` de 6 caracteres alfanuméricos minúsculas \
(`[a-z0-9]{6}`). Únicos dentro de la respuesta.
4. **Colores y fuentes**: usa SIEMPRE las CSS variables globales \
`var(--bricks-color-primary)`, `var(--bricks-color-text)`, \
`var(--bricks-color-accent)`, `var(--bricks-color-bg)`, \
`var(--bricks-color-secondary)`. NO inlines hex hardcodeados salvo si la \
sección tiene un color único no presente en la paleta.
5. **Imágenes**: usa `settings.image = {url, external: true}` apuntando al CDN \
del origen (la URL viene en el HTML adjunto). NO descargues ni reescribas URLs.
6. **Headings**: respeta el tag semántico (h1/h2/h3 según el origen).
7. **Texto**: párrafos largos van en elementos `text` con HTML preservado \
(incluyendo strong/em/a inline). Listas (`<ul>`, `<ol>`) son también `text` \
con el HTML del ul/ol.
8. **Botones**: `button` con `settings = {text, link: {type, url}, style}`.
9. **Si no puedes reproducir un sub-elemento con nativos** (animación compleja, \
SVG inline elaborado, widget Wix sin equivalente Bricks), OMÍTELO y deja una \
nota en el output. NO uses elementos no listados.
10. Devuelve SIEMPRE invocando la tool `emit_bricks_elements`."""


#: JSON Schema de la tool. Riguroso para que Claude no devuelva basura.
TOOL_SCHEMA: dict[str, Any] = {
    "name": "emit_bricks_elements",
    "description": (
        "Emite el array de elementos Bricks que reproducen la sección "
        "del origen. Cada elemento es atómico (id, name, parent, "
        "children, settings)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "elements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "pattern": "^[a-z0-9]{6}$",
                        },
                        "name": {
                            "type": "string",
                            "enum": [
                                "section", "container", "block", "div",
                                "heading", "text", "text-basic",
                                "image", "video", "icon", "icon-box",
                                "button", "accordion", "slider-nested",
                                "nav-nested", "nav-menu", "form",
                                "shortcode", "divider", "spacer", "code",
                            ],
                        },
                        "parent": {"type": "string"},
                        "children": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "settings": {"type": "object"},
                        "label": {"type": "string"},
                    },
                    "required": ["id", "name", "parent"],
                },
                "minItems": 1,
            },
            "notes": {
                "type": "string",
                "description": (
                    "Notas opcionales sobre sub-elementos no migrables "
                    "(animaciones, widgets exóticos). Aparecerán como "
                    "tarea residual."
                ),
            },
        },
        "required": ["elements"],
    },
}


@dataclass
class ClaudeVisionResult:
    """Resultado de una llamada a Claude Vision.

    - `elements`: lista de dicts con shape Bricks.
    - `notes`: notas que el modelo dejó sobre cosas no migrables.
    - `tokens_in` / `tokens_out` / `cost_usd`: telemetría para tracking.
    - `cache_hit`: True si vino del cache `ai_section_cache`.
    """

    elements: list[dict[str, Any]]
    notes: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model: str = DEFAULT_MODEL
    cache_hit: bool = False


def compute_input_hash(
    screenshot: bytes, html: str, selector: str
) -> str:
    """sha256(screenshot + html + selector). Estable entre runs y proyectos.

    El operador puede invalidar el cache cambiando cualquier input.
    `selector` se incluye porque la misma estructura HTML puede vivir
    en distintos sitios del DOM (header vs footer del mismo brand) y
    el screenshot recortado puede diferir.
    """
    h = hashlib.sha256()
    h.update(screenshot)
    h.update(html.encode("utf-8", errors="replace"))
    h.update(selector.encode("utf-8"))
    return h.hexdigest()


def _compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """USD con 6 decimales. Si el modelo no está en `PRICING_USD_PER_MTOK`,
    devuelve 0.0 (telemetría conservadora — mejor undercount que sobre)."""
    pricing = PRICING_USD_PER_MTOK.get(model)
    if not pricing:
        return 0.0
    in_price, out_price = pricing
    return (tokens_in * in_price + tokens_out * out_price) / 1_000_000


class ClaudeVisionClient:
    """Cliente async sobre Anthropic SDK con vision + tool_use.

    Uso:
        client = ClaudeVisionClient(api_key=os.environ["ANTHROPIC_API_KEY"])
        result = await client.transpile_section(
            screenshot_png=screenshot_bytes,
            html="<section>...</section>",
            selector="#comp-hero",
            project_id=42,
            session=db_session,  # opcional, habilita cache
        )
        result.elements  # list[dict] con elementos Bricks
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        sdk_client: Any = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.retries = retries
        if sdk_client is not None:
            # Inyección para tests.
            self._client = sdk_client
        else:
            from anthropic import AsyncAnthropic

            # `max_retries=0` desactiva el retry interno del SDK
            # Anthropic (que reintenta indefinidamente con backoff
            # exponencial en 429/5xx). Nosotros gestionamos el retry
            # con `_call_with_retry` que tiene cap fijo `retries=3`.
            # Sin esto, un rate-limit del tier bajo bloquea el agente
            # durante horas (SDK retry × nuestro retry).
            self._client = AsyncAnthropic(
                api_key=api_key,
                timeout=timeout_s,
                max_retries=0,
            )

    async def transpile_section(
        self,
        *,
        screenshot_png: bytes,
        html: str,
        selector: str,
        project_id: int,
        session: Any = None,
    ) -> ClaudeVisionResult:
        """Pide a Claude reproducir la sección. Usa cache si está disponible.

        Si `session` está pasado (SQLAlchemy Session sync), lee y escribe
        en `ai_section_cache`. Sin session → no hay cache (cada call es
        cobrada).
        """
        input_hash = compute_input_hash(screenshot_png, html, selector)

        # Cache lookup.
        if session is not None:
            cached = self._lookup_cache(session, input_hash)
            if cached is not None:
                log.info(
                    "claude_vision_cache_hit",
                    extra={"input_hash": input_hash[:12], "project_id": project_id},
                )
                cached.cache_hit = True
                return cached

        # Llamada con retry.
        result = await self._call_with_retry(
            screenshot_png=screenshot_png,
            html=html,
            selector=selector,
        )

        # Persistir en cache.
        if session is not None:
            self._save_cache(session, input_hash, project_id, result)

        return result

    # ---------- internals ----------

    async def _call_with_retry(
        self,
        *,
        screenshot_png: bytes,
        html: str,
        selector: str,
    ) -> ClaudeVisionResult:
        """Retry exponencial con jitter en errores transitorios (5xx, 429)."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                return await self._call_once(
                    screenshot_png=screenshot_png,
                    html=html,
                    selector=selector,
                )
            except ClaudeVisionAuthError:
                # 401/403 nunca son retriables.
                raise
            except ClaudeVisionInvalidOutputError as e:
                # Output inválido — el operador prefiere fallback rápido.
                last_error = e
                raise
            except ClaudeVisionApiError as e:
                last_error = e
                if attempt == self.retries - 1:
                    raise
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                log.warning(
                    "claude_vision_retry",
                    extra={"attempt": attempt + 1, "wait_s": wait, "error": str(e)[:120]},
                )
                await asyncio.sleep(wait)
        # No debería llegarse aquí, pero defensive.
        raise ClaudeVisionApiError(
            f"Failed after {self.retries} retries: {last_error}"
        )

    async def _call_once(
        self,
        *,
        screenshot_png: bytes,
        html: str,
        selector: str,
    ) -> ClaudeVisionResult:
        """Una sola llamada al endpoint messages.create con vision + tool_use."""
        import base64

        b64 = base64.standard_b64encode(screenshot_png).decode("ascii")

        # Truncar HTML para no quemar tokens (límite ~32KB ~ 8K tokens).
        max_html_chars = 32 * 1024
        if len(html) > max_html_chars:
            html = html[:max_html_chars] + "\n<!-- TRUNCATED -->"

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                tools=[TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "emit_bricks_elements"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    f"Selector de la sección: `{selector}`\n\n"
                                    f"HTML del origen:\n```html\n{html}\n```\n\n"
                                    "Invoca `emit_bricks_elements` con la "
                                    "lista de elementos Bricks que reproduce "
                                    "esta sección."
                                ),
                            },
                        ],
                    }
                ],
            )
        except Exception as e:  # noqa: BLE001 — Anthropic SDK múltiples tipos
            # Distinguir auth de 5xx por mensaje (Anthropic SDK 0.40+
            # tiene `AuthenticationError` distinta de `APIStatusError`).
            err_type = type(e).__name__
            msg = str(e)[:200]
            if "Authentication" in err_type or "401" in msg or "403" in msg:
                raise ClaudeVisionAuthError(msg) from e
            raise ClaudeVisionApiError(f"{err_type}: {msg}") from e

        # Parsear tool_use block.
        tool_block = None
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                tool_block = block
                break
        if tool_block is None:
            raise ClaudeVisionInvalidOutputError(
                "Claude no invocó la tool emit_bricks_elements"
            )

        tool_input = tool_block.input or {}
        elements = tool_input.get("elements") or []
        if not isinstance(elements, list) or not elements:
            raise ClaudeVisionInvalidOutputError(
                f"`elements` vacío o no-lista: {type(elements).__name__}"
            )

        notes = tool_input.get("notes") or ""
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        cost = _compute_cost(self.model, tokens_in, tokens_out)

        return ClaudeVisionResult(
            elements=elements,
            notes=notes,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            model=self.model,
        )

    def _lookup_cache(self, session: Any, input_hash: str) -> ClaudeVisionResult | None:
        """Lookup en `ai_section_cache` por input_hash. Sync (SQLAlchemy
        Session normal). Devuelve None si no hay hit."""
        try:
            from sqlalchemy import select

            from wcm_db.models.ai_section_cache import AiSectionCache

            row = session.execute(
                select(AiSectionCache).where(
                    AiSectionCache.input_hash == input_hash
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            payload = row.response_json or {}
            return ClaudeVisionResult(
                elements=payload.get("elements") or [],
                notes=payload.get("notes") or "",
                tokens_in=row.tokens_in,
                tokens_out=row.tokens_out,
                cost_usd=row.cost_usd,
                model=row.model,
            )
        except Exception as e:  # noqa: BLE001 — cache fail no debe romper fetch
            log.warning(
                "claude_vision_cache_lookup_failed",
                extra={"error": str(e)[:200]},
            )
            return None

    def _save_cache(
        self,
        session: Any,
        input_hash: str,
        project_id: int,
        result: ClaudeVisionResult,
    ) -> None:
        """Persiste la respuesta en `ai_section_cache`. Fail-safe — si la
        BD rechaza (p.ej. UNIQUE race), log warning sin levantar."""
        try:
            from wcm_db.models.ai_section_cache import AiSectionCache

            entry = AiSectionCache(
                input_hash=input_hash,
                project_id=project_id,
                response_json={
                    "elements": result.elements,
                    "notes": result.notes,
                },
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
            session.add(entry)
            session.flush()
        except Exception as e:  # noqa: BLE001
            log.warning(
                "claude_vision_cache_save_failed",
                extra={"error": str(e)[:200], "project_id": project_id},
            )
            try:
                session.rollback()
            except Exception:
                pass


def make_client_from_env() -> ClaudeVisionClient | None:
    """Helper para AiAssistAgent: construye cliente leyendo
    `ANTHROPIC_API_KEY`. None si no está configurada (el agente caerá a
    RAW_HTML para todos los bloques candidatos)."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        log.warning("claude_vision_no_api_key")
        return None
    return ClaudeVisionClient(api_key=key)
