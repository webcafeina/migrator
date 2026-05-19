"""Comandos sobre el singleton `email_layouts` (v0.14.0 + v0.15.0).

- `wcm email-layout show [--html-file FILE] [--css-file FILE]` —
  imprime el layout actual o lo vuelca a fichero.
- `wcm email-layout update --html FILE [--css FILE]` — reemplaza el
  layout maestro (PUT al backend). Admin-only. Desactiva el tema
  visual si lo había.
- `wcm email-layout theme show` — imprime el `theme_config` actual (JSON).
- `wcm email-layout theme reset` — restaura el tema Webcafeína por
  defecto. Confirmación obligatoria.
- `wcm email-layout theme set --cta-bg HEX --font Inter ...` —
  modifica campos puntuales del tema activo (v0.15.0). Si no había
  tema, parte del default y aplica los cambios.

NO incluye `--inline-html "<html>..."` para evitar pegar HTML largo
en la shell con escapes raros — el operador siempre trabaja con
ficheros.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient
from wcm_cli.errors import CliInputError

app = typer.Typer(help="Layout maestro HTML de los correos de outreach")
theme_app = typer.Typer(help="Tema visual (v0.15.0) — colores, branding, tipografía")
app.add_typer(theme_app, name="theme")

# Defaults Webcafeína — espejo de `default_theme()` del backend. Se usan
# en `theme reset` y como base de `theme set` si no había tema previo.
_DEFAULT_THEME: dict[str, object] = {
    "cta_bg": "#B1F100",
    "cta_text": "#0E1218",
    "cta_border": "#94C800",
    "page_bg": "#F5F6F8",
    "card_bg": "#FFFFFF",
    "card_border": "#E5E7EB",
    "text_color": "#1F2937",
    "text_strong": "#0E1218",
    "link_color": "#5A8A00",
    "footer_text": "#6B7280",
    "brand_accent": "#5A8A00",
    "show_logo": True,
    "logo_url_override": None,
    "logo_max_width_px": 160,
    "font_family": "system-ui",
    "body_font_size_px": 15,
    "body_line_height": 1.65,
    "brand_text_size_px": 22,
    "card_max_width_px": 600,
    "content_padding_px": 28,
    "header_padding_px": 28,
    "footer_padding_px": 18,
    "card_border_radius_px": 6,
    "cta_border_radius_px": 4,
    "card_border_width_px": 1,
}


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
    output.success(f"Layout actualizado · {len(html)} chars HTML / {len(css)} chars CSS")


# ===== v0.15.0: subcomando `theme` =====


@theme_app.command("show")
def theme_show() -> None:
    """Imprime el `theme_config` actual del layout en JSON pretty.

    Si el layout fue editado a mano (modo Código), `theme_config` es
    NULL y este comando lo indica. Para activar el modo Visual usa
    `wcm email-layout theme reset`.
    """
    client = ApiClient()
    layout = client.get("/api/v1/email-layout")
    theme = layout.get("theme_config")
    if theme is None:
        output.info(
            "theme_config = NULL — el layout actual es código manual. "
            "Usa `wcm email-layout theme reset` para activar el tema visual."
        )
        return
    typer.echo(json.dumps(theme, indent=2, ensure_ascii=False, sort_keys=True))


@theme_app.command("reset")
def theme_reset(
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Confirmación explícita — sobrescribe layout_html/css con los defaults.",
        ),
    ] = False,
) -> None:
    """Restaura el tema Webcafeína por defecto. Sobrescribe el HTML/CSS
    actual con la versión canónica. Requiere `--confirm` (operación
    destructiva: tu HTML/CSS personalizado se perderá).
    """
    if not confirm:
        raise CliInputError("Operación destructiva. Vuelve a ejecutar con `--confirm`.")
    client = ApiClient()
    client.put("/api/v1/email-layout", json={"theme_config": _DEFAULT_THEME})
    output.success("Tema restaurado al default Webcafeína.")


# Flags de `theme set` — uno por cada campo del schema EmailLayoutTheme.
# typer.Option se traduce a `--color-cta-bg` (snake_case → kebab-case).
@theme_app.command("set")
def theme_set(
    cta_bg: Annotated[str | None, typer.Option(help="Color HEX del fondo del CTA")] = None,
    cta_text: Annotated[str | None, typer.Option(help="Color HEX del texto del CTA")] = None,
    cta_border: Annotated[str | None, typer.Option(help="Color HEX del borde del CTA")] = None,
    page_bg: Annotated[str | None, typer.Option(help="Color HEX del fondo de la página")] = None,
    card_bg: Annotated[str | None, typer.Option(help="Color HEX del fondo del card")] = None,
    card_border: Annotated[str | None, typer.Option(help="Color HEX del borde del card")] = None,
    text_color: Annotated[str | None, typer.Option(help="Color HEX del texto principal")] = None,
    text_strong: Annotated[str | None, typer.Option(help="Color HEX del texto destacado")] = None,
    link_color: Annotated[str | None, typer.Option(help="Color HEX de los links")] = None,
    footer_text: Annotated[str | None, typer.Option(help="Color HEX del texto del footer")] = None,
    brand_accent: Annotated[str | None, typer.Option(help="Color HEX del acento de marca")] = None,
    font_family: Annotated[
        str | None,
        typer.Option(help="Fuente: system-ui | serif | Inter"),
    ] = None,
    show_logo: Annotated[
        bool | None,
        typer.Option("--show-logo/--no-show-logo", help="Mostrar logo (vs texto estilado)"),
    ] = None,
    logo_url_override: Annotated[
        str | None,
        typer.Option(help="URL alternativa del logo (vacío para usar EMAIL_LOGO_URL)"),
    ] = None,
    card_max_width_px: Annotated[
        int | None,
        typer.Option(help="Ancho máximo del card (320-720)"),
    ] = None,
) -> None:
    """Modifica campos puntuales del tema. Si no había tema previo
    parte de los defaults Webcafeína y aplica solo los flags que pases.

    Para una edición exhaustiva, mejor usa la UI en
    `/settings/email-layout`. Este comando es para scripts/CI/ajustes
    rápidos en producción.
    """
    client = ApiClient()
    current = client.get("/api/v1/email-layout")
    existing_theme = current.get("theme_config") or dict(_DEFAULT_THEME)

    overrides: dict[str, object] = {}
    locals_dict = locals()
    for field in (
        "cta_bg",
        "cta_text",
        "cta_border",
        "page_bg",
        "card_bg",
        "card_border",
        "text_color",
        "text_strong",
        "link_color",
        "footer_text",
        "brand_accent",
        "font_family",
        "show_logo",
        "logo_url_override",
        "card_max_width_px",
    ):
        value = locals_dict.get(field)
        if value is not None:
            overrides[field] = value

    if not overrides:
        raise CliInputError("No has pasado ningún flag. Ejemplo: `--cta-bg #ff0000`.")

    new_theme = {**existing_theme, **overrides}
    client.put("/api/v1/email-layout", json={"theme_config": new_theme})
    output.success(
        f"Tema actualizado · {len(overrides)} campos modificados: "
        f"{', '.join(sorted(overrides.keys()))}"
    )
