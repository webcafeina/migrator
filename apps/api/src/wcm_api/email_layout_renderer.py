"""Generador del HTML+CSS canónico del layout maestro a partir de un tema.

v0.15.0 — cuando el operador edita visualmente el layout en
`/settings/email-layout` tab "Visual", el frontend envía un
`EmailLayoutTheme` (JSON). Este módulo lo convierte en (`layout_html`,
`layout_css`) email-safe que se persiste en `email_layouts` y se
inyecta en cada correo por el composer.

La plantilla canónica vive aquí (no en BD) porque es CÓDIGO de la
marca Webcafeína — su estructura define el aspecto de TODOS los
correos. Cambios estructurales (añadir secciones, cambiar el orden
del header) requieren tocar este módulo y desplegar.

## Por qué `string.Template` y no Jinja2

El output debe ser un fichero Jinja2 válido para que el composer lo
renderice luego con los datos reales (`content`, `company_legal_name`,
`opt_out_url`, etc). Si usáramos Jinja2 aquí, los `{{ content | safe }}`
del template canónico se resolverían (incorrectamente) en este paso.

`string.Template` usa sintaxis `$nombre` que NO colisiona con `{{ ... }}`
de Jinja2 ni con las llaves de CSS. Resolvemos solo las vars del tema
($cta_bg, $card_max_width_px, …) y los slots del composer quedan
intactos en el output.

Función pura: misma entrada → misma salida. Testeable sin BD. Idempotente.
"""

from __future__ import annotations

from string import Template

from wcm_types.schemas.outreach import EmailLayoutTheme

# Plantilla HTML maestra. Usa `$nombre` para vars del tema y deja los
# `{{ ... }}` de Jinja2 intactos (los rellena el composer al renderizar
# cada correo). El bloque `${maybe_logo_img_or_brand_text}` se computa
# en Python (lógica condicional show_logo) — Template no soporta if/else
# nativamente, así que pre-cocemos el bloque alternativo.
_LAYOUT_TEMPLATE = Template("""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ subject | default('Webcafeína') }}</title>
</head>
<body class="wcm-body">
<table role="presentation" class="wcm-wrap" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr>
    <td align="center">
      <table role="presentation" class="wcm-card" cellpadding="0" cellspacing="0" border="0" width="$card_max_width_px">
        <tr>
          <td class="wcm-header">
$header_block
          </td>
        </tr>
        <tr>
          <td class="wcm-content">
            {{ content | safe }}
            {% if cta_label and cta_url %}
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" class="wcm-cta-wrap">
                <tr>
                  <td align="left">
                    <a href="{{ cta_url }}" class="wcm-cta">{{ cta_label }} &rarr;</a>
                  </td>
                </tr>
              </table>
            {% endif %}
          </td>
        </tr>
        <tr>
          <td class="wcm-footer">
            <p class="wcm-footer-line">
              {{ company_legal_name }}{% if company_cif %} &middot; CIF {{ company_cif }}{% endif %}{% if company_address %} &middot; {{ company_address }}{% endif %}
            </p>
            <p class="wcm-footer-line">
              <a href="mailto:{{ company_contact_email }}" class="wcm-footer-link">{{ company_contact_email }}</a>
              &middot;
              <a href="{{ privacy_policy_url }}" class="wcm-footer-link">Política de privacidad</a>
              &middot;
              <a href="{{ opt_out_url }}" class="wcm-footer-link">Darme de baja</a>
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
""")

# Bloques alternativos del header según `show_logo` (Template no
# soporta if/else; los pre-cocemos en Python).
_HEADER_LOGO_IMG = Template(
    '            {% if logo_url %}<img src="{{ logo_url }}" alt="Webcafeína" width="$logo_max_width_px" class="wcm-logo">'
    '{% else %}<span class="wcm-brand-text">webcafe<span class="wcm-brand-accent">í</span>na</span>{% endif %}'
)
_HEADER_LOGO_OVERRIDE = Template(
    '            <img src="$logo_url_override" alt="Webcafeína" width="$logo_max_width_px" class="wcm-logo">'
)
_HEADER_BRAND_TEXT = '            <span class="wcm-brand-text">webcafe<span class="wcm-brand-accent">í</span>na</span>'


# CSS canónico parametrizado. Premailer lo inline-eará al enviar. Sin
# media queries, sin pseudo-clases. Las llaves de CSS van escapadas
# como `$$` en string.Template para no chocar con la sustitución de
# `$nombre`... pero como NO uso `$` en CSS estándar, basta con
# escapar usando Template.safe_substitute (ignora $ que no coincidan
# con un identificador) — sigo usando substitute() porque queremos
# fallar si falta una var del tema. Resuelvo el dilema escapando
# las pocas `$` que aparezcan (none por ahora).
_CSS_TEMPLATE = Template(""".wcm-body { margin: 0; padding: 0; background-color: $page_bg; font-family: $font_stack; color: $text_color; }
.wcm-wrap { background-color: $page_bg; padding: 32px 12px; }
.wcm-card { background-color: $card_bg; border-radius: ${card_border_radius_px}px; border: ${card_border_width_px}px solid $card_border; }
.wcm-header { padding: ${header_padding_px}px ${content_padding_px}px 16px ${content_padding_px}px; border-bottom: 1px solid #F1F2F4; }
.wcm-logo { display: block; height: auto; max-width: ${logo_max_width_px}px; }
.wcm-brand-text { font-size: ${brand_text_size_px}px; font-weight: 700; letter-spacing: -0.01em; color: $text_strong; }
.wcm-brand-accent { color: $brand_accent; }
.wcm-content { padding: ${content_padding_px}px ${content_padding_px}px 8px ${content_padding_px}px; font-size: ${body_font_size_px}px; line-height: $body_line_height; color: $text_color; }
.wcm-content p { margin: 0 0 14px 0; }
.wcm-content a { color: $link_color; text-decoration: underline; }
.wcm-content strong { font-weight: 600; color: $text_strong; }
.wcm-content ul, .wcm-content ol { margin: 0 0 14px 22px; padding: 0; }
.wcm-content li { margin: 0 0 4px 0; }
.wcm-cta-wrap { margin: 8px 0 18px 0; }
.wcm-cta { display: inline-block; background-color: $cta_bg; color: $cta_text; text-decoration: none; font-weight: 700; font-size: 14px; padding: 12px 20px; border-radius: ${cta_border_radius_px}px; border: 1px solid $cta_border; }
.wcm-footer { padding: ${footer_padding_px}px ${content_padding_px}px ${footer_padding_px}px ${content_padding_px}px; border-top: 1px solid #F1F2F4; }
.wcm-footer-line { margin: 4px 0; font-size: 11.5px; line-height: 1.5; color: $footer_text; }
.wcm-footer-link { color: $footer_text; text-decoration: underline; }
""")


# Mapeo font_family → font-stack CSS completo email-safe.
_FONT_STACKS: dict[str, str] = {
    "system-ui": (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    ),
    "serif": "Georgia, 'Times New Roman', Times, serif",
    "Inter": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
}


def _build_header_block(theme: EmailLayoutTheme) -> str:
    """Pre-coce el bloque del header según los toggles del tema.

    3 casos:
    - show_logo=False → texto estilado siempre.
    - show_logo=True + logo_url_override → <img> con override fijo.
    - show_logo=True sin override → Jinja2 condicional {% if logo_url %}
      (el composer decide en runtime según EMAIL_LOGO_URL del env).
    """
    if not theme.show_logo:
        return _HEADER_BRAND_TEXT
    if theme.logo_url_override:
        return _HEADER_LOGO_OVERRIDE.substitute(
            logo_url_override=theme.logo_url_override,
            logo_max_width_px=theme.logo_max_width_px,
        )
    return _HEADER_LOGO_IMG.substitute(logo_max_width_px=theme.logo_max_width_px)


def generate_layout_from_theme(theme: EmailLayoutTheme) -> tuple[str, str]:
    """Devuelve `(layout_html, layout_css)` renderizado a partir del tema.

    Función pura — sin side effects, sin BD, sin red. Misma entrada
    devuelve siempre la misma salida (testeable con idempotencia).

    El HTML y CSS resultantes son los que se persisten en
    `email_layouts.layout_html` / `layout_css` cuando el operador
    guarda desde el tab Visual.
    """
    font_stack = _FONT_STACKS.get(theme.font_family, _FONT_STACKS["system-ui"])
    header_block = _build_header_block(theme)

    html = _LAYOUT_TEMPLATE.substitute(
        card_max_width_px=theme.card_max_width_px,
        header_block=header_block,
    )
    css = _CSS_TEMPLATE.substitute(
        page_bg=theme.page_bg,
        card_bg=theme.card_bg,
        card_border=theme.card_border,
        card_border_radius_px=theme.card_border_radius_px,
        card_border_width_px=theme.card_border_width_px,
        text_color=theme.text_color,
        text_strong=theme.text_strong,
        brand_accent=theme.brand_accent,
        link_color=theme.link_color,
        cta_bg=theme.cta_bg,
        cta_text=theme.cta_text,
        cta_border=theme.cta_border,
        cta_border_radius_px=theme.cta_border_radius_px,
        footer_text=theme.footer_text,
        body_font_size_px=theme.body_font_size_px,
        body_line_height=theme.body_line_height,
        brand_text_size_px=theme.brand_text_size_px,
        logo_max_width_px=theme.logo_max_width_px,
        header_padding_px=theme.header_padding_px,
        footer_padding_px=theme.footer_padding_px,
        content_padding_px=theme.content_padding_px,
        font_stack=font_stack,
    )
    return html, css
