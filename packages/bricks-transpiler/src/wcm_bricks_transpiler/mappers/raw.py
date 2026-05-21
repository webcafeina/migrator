"""Mapper para bloques RAW_HTML (sprint v0.22.0, fallback de ai_assist).

Cuando ni la heurística ni Claude Vision pueden reproducir una sección
con elementos Bricks nativos, el `AiAssistAgent` marca el bloque como
`BlockType.RAW_HTML` con `content_json = {html, css}`.

Este mapper emite UN solo elemento Bricks `code` con:
- `code` = `<div data-wcm-block="<hash>">{html}</div><style>{namespaced_css}</style>`
- `executeCode = True` para que Bricks renderice como HTML (no como
  texto formateado).
- `noRoot = False` para que el code element tenga el wrapper estándar
  de Bricks.

El CSS se prefija con `[data-wcm-block="<hash>"]` para aislar las
reglas — sin esto, las reglas del origen contaminarían el resto de la
página (Bricks `code` element NO tiene sandbox CSS).

CSS namespace via `tinycss2`:
- Cada selector de cada `QualifiedRule` se prefija.
- `@media`/`@supports` se procesan recursivamente (las reglas internas
  se namespacean).
- `@font-face` y `@keyframes` se preservan tal cual (son globales por
  necesidad — animations referenciadas desde dentro del namespace
  siguen funcionando).
- `@import` se elimina (Bricks `code` no las carga en orden correcto
  y suelen ser causa de leaks).

Si tinycss2 falla parseando, fallback regex conservador (prefijo simple
sin entender nested at-rules).
"""

from __future__ import annotations

import hashlib
from typing import Any

from wcm_bricks_transpiler.mappers._types import (
    MapperContext,
    MapperResult,
    ResidualHint,
)
from wcm_bricks_transpiler.schema import BricksElement
from wcm_types.enums import BlockType

#: At-rules que NO se namespacean (son globales por su naturaleza).
_PRESERVED_AT_RULES = frozenset({"font-face", "keyframes", "charset", "page"})


def map_raw_html(
    block: dict[str, Any],
    order_index: int,
    block_type: BlockType,
    parent_id: str,
    ctx: MapperContext,
) -> MapperResult:
    """Emite un elemento Bricks `code` con HTML+CSS namespaceado."""
    html: str = block.get("html") or ""
    css: str = block.get("css") or ""

    if not html.strip():
        return MapperResult(
            residual=ResidualHint(
                title=f"Bloque RAW vacío (orden {order_index})",
                description=(
                    "El bloque RAW_HTML no tiene `html`. Posible causa: el "
                    "extractor marcó UNKNOWN sin guardar raw_html. Revisar "
                    "ai_assist log."
                ),
                estimated_minutes=5,
            )
        )

    # Hash determinista del bloque para namespace estable entre runs.
    # `order_index + html[:200]` es suficiente — colisión astronómica.
    block_id = _block_namespace_id(order_index, html)

    sanitized_html = _sanitize_html(html)
    namespaced_css, css_residual = _namespace_css(css, block_id)

    wrapped = (
        f'<div data-wcm-block="{block_id}">{sanitized_html}</div>'
        f"<style>{namespaced_css}</style>"
    )

    el = BricksElement(
        id=ctx.id_gen.fresh(order_index, "raw"),
        name="code",
        parent=parent_id,
        children=[],
        settings={
            "code": wrapped,
            "executeCode": True,
            "noRoot": False,
        },
        label=f"RAW {block_id}",
    )

    residual: ResidualHint | None = None
    if css_residual:
        residual = ResidualHint(
            title=f"CSS namespace incompleto en RAW (orden {order_index})",
            description=(
                f"El parser tinycss2 falló al procesar parte del CSS de "
                f"la sección (block_id={block_id}). Algunas reglas pueden "
                f"filtrarse fuera del bloque. Detalle: {css_residual}. "
                "Revisar inspector del navegador y reescribir manualmente "
                "selectores conflictivos."
            ),
            estimated_minutes=15,
        )

    return MapperResult(elements=[el], residual=residual)


# ---------- helpers ----------


def _block_namespace_id(order_index: int, html: str) -> str:
    """6 chars hex, estable entre runs. Compatible con regex `[a-z0-9]{6}`."""
    h = hashlib.sha256()
    h.update(str(order_index).encode())
    h.update(html[:200].encode("utf-8", errors="replace"))
    return h.hexdigest()[:6]


def _sanitize_html(html: str) -> str:
    """Elimina patrones peligrosos del HTML antes de inyectar.

    Bricks ejecuta el code element con `executeCode=true` que renderiza
    HTML como tal pero también puede ejecutar PHP si el origen incluye
    `<?php`. Para defensa básica:
    - Elimina `<script>...</script>` (impide JS arbitrario).
    - Elimina `<?php ... ?>` literal.
    - Elimina handlers inline `onClick=`, `onLoad=`, etc.
    """
    import re

    # `<script>` block (greedy match con DOTALL).
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    # `<?php ... ?>` o variantes ASP `<%...%>`.
    html = re.sub(r"<\?(?:php)?[\s\S]*?\?>", "", html)
    html = re.sub(r"<%[\s\S]*?%>", "", html)
    # Event handlers inline (`onclick="..."`, `onload='...'`).
    html = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", html, flags=re.IGNORECASE)
    html = re.sub(r"\son\w+\s*=\s*'[^']*'", "", html, flags=re.IGNORECASE)
    return html


def _namespace_css(css: str, block_id: str) -> tuple[str, str | None]:
    """Prefija todas las reglas CSS con `[data-wcm-block="<block_id>"]`.

    Devuelve `(namespaced_css, error_message_or_None)`. Si tinycss2 falla
    parseando, intenta fallback regex; si éste también falla, devuelve
    el CSS original sin namespace + mensaje de error (residual).

    Reglas:
    - `QualifiedRule` (selectores normales): prefijar cada selector.
    - `AtRule` `@media`, `@supports`, `@container`: procesar las
      reglas internas recursivamente.
    - `AtRule` `@font-face`, `@keyframes`, `@charset`, `@page`:
      preservar literal (son globales por necesidad).
    - `@import`: eliminar (no funciona bien en code elements).
    """
    css = (css or "").strip()
    if not css:
        return "", None

    try:
        import tinycss2
    except ImportError:
        return _namespace_css_regex_fallback(css, block_id), "tinycss2 no instalado"

    try:
        rules = tinycss2.parse_stylesheet(
            css, skip_comments=True, skip_whitespace=True
        )
        out_parts: list[str] = []
        for rule in rules:
            piece = _process_rule(rule, block_id, tinycss2)
            if piece is not None:
                out_parts.append(piece)
        return "".join(out_parts), None
    except Exception as e:  # noqa: BLE001 — parser pathológico → fallback
        fallback = _namespace_css_regex_fallback(css, block_id)
        return fallback, f"tinycss2 falló: {type(e).__name__}"


def _process_rule(rule: Any, block_id: str, tinycss2: Any) -> str | None:
    """Procesa una regla de top-level. Devuelve el CSS reescrito o None
    para reglas eliminadas (`@import`)."""
    rule_type = type(rule).__name__

    if rule_type == "QualifiedRule":
        # selectores → prefijar cada uno con `[data-wcm-block="..."] `
        prelude = tinycss2.serialize(rule.prelude).strip()
        body = tinycss2.serialize(rule.content)
        new_selectors = _prefix_selectors(prelude, block_id)
        return f"{new_selectors}{{{body}}}"

    if rule_type == "AtRule":
        at_keyword = (rule.lower_at_keyword or "").lower()
        if at_keyword == "import":
            # Eliminar @import — Bricks code element no los carga limpio.
            return None
        if at_keyword in _PRESERVED_AT_RULES:
            # Globales: preservar tal cual.
            prelude = tinycss2.serialize(rule.prelude).strip()
            if rule.content is None:
                return f"@{rule.at_keyword} {prelude};"
            body = tinycss2.serialize(rule.content)
            return f"@{rule.at_keyword} {prelude}{{{body}}}"
        # @media, @supports, @container, @layer: re-parse interior y
        # namespacear cada qualified-rule dentro.
        prelude = tinycss2.serialize(rule.prelude).strip()
        if rule.content is None:
            return f"@{rule.at_keyword} {prelude};"
        inner_rules = tinycss2.parse_rule_list(
            rule.content, skip_comments=True, skip_whitespace=True
        )
        inner_parts: list[str] = []
        for inner in inner_rules:
            piece = _process_rule(inner, block_id, tinycss2)
            if piece is not None:
                inner_parts.append(piece)
        return f"@{rule.at_keyword} {prelude}{{{''.join(inner_parts)}}}"

    # Tokens sueltos o reglas no reconocidas → conservar.
    return tinycss2.serialize([rule])


def _prefix_selectors(prelude: str, block_id: str) -> str:
    """Por cada selector (separado por coma top-level), prefijar con
    `[data-wcm-block="<id>"]`. Mantiene combinator entre prefix y resto.

    Casos especiales:
    - `:root`, `html`, `body` se reemplazan POR el prefix (NO `[...] :root`):
      no tiene sentido y rompe layout.
    - Selectores que ya contienen `[data-wcm-block]` (re-namespace de
      mismo bloque) se dejan tal cual.
    """
    prefix = f'[data-wcm-block="{block_id}"]'
    parts: list[str] = []
    for sel in _split_selectors_top_level(prelude):
        sel = sel.strip()
        if not sel:
            continue
        if "[data-wcm-block" in sel:
            parts.append(sel)
            continue
        low = sel.lower()
        if low in (":root", "html", "body"):
            parts.append(prefix)
            continue
        # Reglas tipo `:root, html` ya cubiertas arriba; los demás
        # selectores normales: añadir prefix + espacio (descendant).
        parts.append(f"{prefix} {sel}")
    return ",".join(parts)


def _split_selectors_top_level(prelude: str) -> list[str]:
    """Divide selectores por comas top-level (ignorando comas dentro de
    paréntesis `()` o corchetes `[]`). `:is(a,b)` NO se rompe.
    """
    out: list[str] = []
    buf: list[str] = []
    depth_paren = 0
    depth_brack = 0
    for ch in prelude:
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack = max(0, depth_brack - 1)
        elif ch == "," and depth_paren == 0 and depth_brack == 0:
            out.append("".join(buf))
            buf.clear()
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _namespace_css_regex_fallback(css: str, block_id: str) -> str:
    """Fallback conservador si tinycss2 falla. Solo prefija selectores
    simples top-level (heurística pobre, pero mejor que nada).

    NO maneja `@media` internos correctamente — son pasthrough.
    """
    import re

    prefix = f'[data-wcm-block="{block_id}"]'
    # Encontrar bloques `selector { ... }` top-level. Limitado: no
    # gestiona nested at-rules ni colmillos de braces.
    pattern = re.compile(r"([^@{}]+?)\{([^}]*)\}", re.DOTALL)

    def repl(match: re.Match[str]) -> str:
        selectors_raw = match.group(1).strip()
        body = match.group(2)
        new_selectors = ",".join(
            f"{prefix} {s.strip()}" if s.strip() else ""
            for s in selectors_raw.split(",")
        )
        return f"{new_selectors}{{{body}}}"

    return pattern.sub(repl, css)


# Expose for typed import in transpiler tests/registry.
__all__ = ["map_raw_html", "_namespace_css", "_block_namespace_id"]
