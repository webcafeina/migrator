"""Comandos sobre el singleton `email_layouts` (v0.14.0).

- `wcm email-layout show [--html-file FILE] [--css-file FILE]` —
  imprime el layout actual o lo vuelca a fichero.
- `wcm email-layout update --html FILE [--css FILE]` — reemplaza el
  layout maestro (PUT al backend). Admin-only.

NO incluye `--inline-html "<html>..."` para evitar pegar HTML largo
en la shell con escapes raros — el operador siempre trabaja con
ficheros.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient
from wcm_cli.errors import CliInputError

app = typer.Typer(help="Layout maestro HTML de los correos de outreach")


@app.command("show")
def show_layout(
    html_file: Annotated[
        Path | None,
        typer.Option(
            "--html-file",
            help="Si se proporciona, vuelca el HTML al fichero (sin imprimirlo)",
        ),
    ] = None,
    css_file: Annotated[
        Path | None,
        typer.Option(
            "--css-file",
            help="Si se proporciona, vuelca el CSS al fichero",
        ),
    ] = None,
) -> None:
    """Imprime el layout actual (HTML + CSS) o lo vuelca a fichero."""
    client = ApiClient()
    layout = client.get("/api/v1/email-layout")
    html = str(layout.get("layout_html", ""))
    css = str(layout.get("layout_css", ""))

    if html_file:
        html_file.write_text(html, encoding="utf-8")
        output.success(f"HTML escrito en {html_file} ({len(html)} chars)")
    if css_file:
        css_file.write_text(css, encoding="utf-8")
        output.success(f"CSS escrito en {css_file} ({len(css)} chars)")

    if not html_file and not css_file:
        output.info("=== layout_html ===")
        typer.echo(html)
        output.info("=== layout_css ===")
        typer.echo(css)


@app.command("update")
def update_layout(
    html_file: Annotated[
        Path,
        typer.Option("--html", help="Fichero HTML con el layout maestro"),
    ],
    css_file: Annotated[
        Path | None,
        typer.Option(
            "--css",
            help="Fichero CSS opcional (si vacío se mantiene el actual)",
        ),
    ] = None,
) -> None:
    """Reemplaza el layout maestro. Requiere rol admin en el backend.

    El backend valida sintaxis Jinja2 antes de persistir (422 si rota).
    AuditLog `EMAIL_LAYOUT_UPDATE` se escribe con el usuario actor.
    """
    if not html_file.exists():
        raise CliInputError(f"Fichero HTML no encontrado: {html_file}")
    html = html_file.read_text(encoding="utf-8")
    if not html.strip():
        raise CliInputError("layout_html no puede estar vacío")

    client = ApiClient()
    if css_file is None:
        # Conservamos el CSS existente.
        current = client.get("/api/v1/email-layout")
        css = str(current.get("layout_css", ""))
    else:
        if not css_file.exists():
            raise CliInputError(f"Fichero CSS no encontrado: {css_file}")
        css = css_file.read_text(encoding="utf-8")

    client.put(
        "/api/v1/email-layout",
        json={"layout_html": html, "layout_css": css},
    )
    output.success(
        f"Layout actualizado · {len(html)} chars HTML / {len(css)} chars CSS"
    )
