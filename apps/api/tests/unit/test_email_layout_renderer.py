"""Tests del generador canónico de layouts (v0.15.0)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wcm_api.email_layout_renderer import generate_layout_from_theme
from wcm_types.schemas.outreach import EmailLayoutTheme, default_theme


def test_defaults_generate_html_and_css_with_brand_colors() -> None:
    html, css = generate_layout_from_theme(default_theme())
    # HTML debe ser email-safe (tabla 600px del default).
    assert "<table" in html
    assert 'width="600"' in html
    # CSS contiene los hex de marca por defecto.
    assert "#B1F100" in css  # CTA bg lima Webcafeína
    assert "#0E1218" in css  # CTA text dark
    # Slot del contenido presente.
    assert "{{ content | safe }}" in html
    # Footer legal con slots.
    assert "{{ company_legal_name }}" in html
    assert "{{ opt_out_url }}" in html


def test_custom_colors_se_inyectan_en_css() -> None:
    theme = EmailLayoutTheme(
        cta_bg="#FF0000",
        cta_text="#FFFFFF",
        page_bg="#000000",
        link_color="#00FF00",
    )
    _, css = generate_layout_from_theme(theme)
    assert "#FF0000" in css
    assert "#00FF00" in css
    assert "#000000" in css
    # Los colores antiguos NO deben aparecer.
    assert "#B1F100" not in css


def test_card_width_se_aplica_en_html_y_css() -> None:
    theme = EmailLayoutTheme(card_max_width_px=480)
    html, css = generate_layout_from_theme(theme)
    assert 'width="480"' in html
    # El CSS no fija ancho del .wcm-card (el width attribute del table
    # lo controla), pero sí logo_max_width que es independiente.
    assert "480" in css or "max-width" in css


def test_show_logo_false_pinta_brand_text() -> None:
    theme = EmailLayoutTheme(show_logo=False)
    html, _ = generate_layout_from_theme(theme)
    assert "webcafe" in html
    assert "<img" not in html


def test_show_logo_true_sin_override_emite_condicional_jinja2() -> None:
    """Si show_logo=True sin override, el HTML debe contener el bloque
    Jinja2 `{% if logo_url %}<img>{% else %}<span>...{% endif %}` para
    que el composer decida en runtime según EMAIL_LOGO_URL del env.

    Sin EMAIL_LOGO_URL configurado, el composer pintará el span
    (fallback texto estilado). El layout en sí contiene ambos."""
    theme = EmailLayoutTheme(show_logo=True, logo_url_override=None)
    html, _ = generate_layout_from_theme(theme)
    assert "{% if logo_url %}" in html
    assert "<img" in html
    assert "webcafe" in html  # fallback span también presente


def test_font_family_serif_aplica_stack_serif() -> None:
    theme = EmailLayoutTheme(font_family="serif")
    _, css = generate_layout_from_theme(theme)
    assert "Georgia" in css
    assert "serif" in css


def test_font_family_default_aplica_system_ui() -> None:
    theme = EmailLayoutTheme()  # default system-ui
    _, css = generate_layout_from_theme(theme)
    assert "-apple-system" in css
    assert "BlinkMacSystemFont" in css


def test_idempotencia_mismo_theme_mismo_html_css() -> None:
    theme = EmailLayoutTheme(cta_bg="#ABCDEF", card_max_width_px=520)
    html1, css1 = generate_layout_from_theme(theme)
    html2, css2 = generate_layout_from_theme(theme)
    assert html1 == html2
    assert css1 == css2


def test_hex_invalido_rechazado_por_pydantic() -> None:
    with pytest.raises(ValidationError):
        EmailLayoutTheme(cta_bg="rojo")
    with pytest.raises(ValidationError):
        EmailLayoutTheme(cta_bg="#FFF")  # 3 chars, requerimos 6
    with pytest.raises(ValidationError):
        EmailLayoutTheme(cta_bg="#ZZZZZZ")


def test_card_width_fuera_de_rango_rechazado() -> None:
    with pytest.raises(ValidationError):
        EmailLayoutTheme(card_max_width_px=200)  # < 320
    with pytest.raises(ValidationError):
        EmailLayoutTheme(card_max_width_px=1000)  # > 720


def test_font_family_fuera_de_literal_rechazado() -> None:
    with pytest.raises(ValidationError):
        EmailLayoutTheme(font_family="Comic Sans")  # type: ignore[arg-type]


def test_extra_keys_se_ignoran_en_theme_legacy() -> None:
    """JSONs antiguos con campos extra (cuando añadamos campos nuevos
    en el futuro) no deben romper la lectura — model_config extra='ignore'."""
    theme = EmailLayoutTheme.model_validate({"cta_bg": "#B1F100", "campo_inexistente_futuro": "x"})
    assert theme.cta_bg == "#B1F100"
