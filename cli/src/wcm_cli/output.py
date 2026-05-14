"""Output con Rich aplicando paleta Webcafeína.

Reglas (CLAUDE.md §3):
- Texto claro: #F2E8D2
- Acento lima #B1F100 solo para CTAs, numeración, datos clave
- Detalle marrón #5A3519 para metadatos secundarios

Para mensajes simples usamos `typer.echo()` (que cumple con CliRunner sin
problemas de buffering). Para tablas y output denso usamos Rich Console.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import typer
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.theme import Theme

#: Paleta Webcafeína mapeada a Rich styles.
_WCM_THEME = Theme({
    "accent": Style(color="#B1F100", bold=True),
    "primary": Style(color="#F2E8D2"),
    "secondary": Style(color="#5A3519"),
    "success": Style(color="#B1F100", bold=True),
    "warning": Style(color="#FFAB00", bold=True),
    "error": Style(color="#FF5252", bold=True),
    "muted": Style(color="#7d6552", italic=True),
})


def _console() -> Console:
    """Construye una Console que respeta el `sys.stdout` actual.

    Crítico para tests con `CliRunner`: Rich cachea el stream al
    instanciar, así que un singleton no captura redirecciones de pytest.
    """
    return Console(theme=_WCM_THEME, file=sys.stdout, force_terminal=False, highlight=False)


def _err_console() -> Console:
    return Console(theme=_WCM_THEME, file=sys.stderr, force_terminal=False, highlight=False)


def is_json_mode() -> bool:
    return os.environ.get("WCM_JSON", "").lower() in ("1", "true", "yes")


def set_json_mode(enabled: bool) -> None:
    os.environ["WCM_JSON"] = "1" if enabled else "0"


# ---------- mensajes simples (typer.echo, sin Rich buffering) ----------

def header(title: str) -> None:
    """Línea de título con marca. Sin separador denso para no romper widths."""
    if is_json_mode():
        return
    typer.echo(f"━━ {title} ━━")


def success(message: str) -> None:
    if is_json_mode():
        return
    typer.echo(f"✓ {message}")


def info(message: str) -> None:
    if is_json_mode():
        return
    typer.echo(message)


def warning(message: str) -> None:
    typer.echo(f"⚠ {message}", err=is_json_mode())


def error(message: str, *, hint: str | None = None) -> None:
    """Imprime un error.

    En modo --json va a stderr (mantiene stdout JSON-limpio).
    En modo humano va a stdout para que `runner.invoke().output` lo capture.
    """
    typer.echo(f"✕ {message}", err=is_json_mode())
    if hint:
        typer.echo(f"  hint: {hint}", err=is_json_mode())


def key_value(items: dict[str, Any]) -> None:
    if is_json_mode():
        emit_json(items)
        return
    for k, v in items.items():
        typer.echo(f"  {k}: {v}")


# ---------- tablas (Rich) ----------

def render_table(
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    json_payload: list[dict] | None = None,
) -> None:
    """Renderiza tabla con paleta. En modo JSON, emite `json_payload`."""
    if is_json_mode():
        if json_payload is not None:
            emit_json(json_payload)
        else:
            emit_json([dict(zip(columns, r, strict=False)) for r in rows])
        return

    table = Table(title=title, title_style="accent", border_style="secondary")
    for col in columns:
        table.add_column(col, header_style="accent")
    for row in rows:
        table.add_row(*(str(v) if v is not None else "—" for v in row))
    _console().print(table)


# ---------- JSON ----------

def emit_json(payload: Any) -> None:
    """Imprime JSON limpio a stdout sin colores. Útil para piping a `jq`."""
    json.dump(payload, sys.stdout, ensure_ascii=False, default=str, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()
