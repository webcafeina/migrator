"""Tests del helper html_email (v0.14.0)."""

from __future__ import annotations

from wcm_worker.integrations.html_email import (
    html_to_text,
    inline_css,
    is_html,
    wrap_plain_as_html,
)

# --- is_html ---


def test_is_html_recognises_paragraph_tag() -> None:
    assert is_html("<p>Hola</p>") is True


def test_is_html_recognises_anchor() -> None:
    assert is_html('text <a href="x">link</a> more') is True


def test_is_html_false_on_plain_text() -> None:
    assert is_html("Hola, esto es texto") is False


def test_is_html_false_on_lt_without_known_tag() -> None:
    """`<3 días>` o URLs con `<` no deben dispararlo (edge case del plan)."""
    assert is_html("Tardamos <3 días en migrar") is False
    assert is_html("https://example.com/?q=<unknown>") is False


def test_is_html_false_on_empty() -> None:
    assert is_html("") is False
    assert is_html(None) is False


# --- wrap_plain_as_html ---


def test_wrap_plain_as_html_creates_paragraphs() -> None:
    out = wrap_plain_as_html("Hola.\n\nQué tal.")
    assert "<p>Hola.</p>" in out
    assert "<p>Qué tal.</p>" in out


def test_wrap_plain_as_html_escapes_special_chars() -> None:
    out = wrap_plain_as_html("a < b & c > d")
    assert "&lt;" in out
    assert "&amp;" in out
    assert "&gt;" in out


def test_wrap_plain_as_html_single_newlines_become_br() -> None:
    out = wrap_plain_as_html("línea 1\nlínea 2")
    assert "<br>" in out


def test_wrap_plain_as_html_empty_returns_empty() -> None:
    assert wrap_plain_as_html("") == ""


# --- inline_css ---


def test_inline_css_inlines_style_to_attribute() -> None:
    html = "<html><body><p>Hi</p></body></html>"
    css = "p { color: red; }"
    out = inline_css(html, css)
    assert 'style="color' in out  # algún atributo style en <p>
    assert "red" in out


def test_inline_css_idempotent_on_no_css() -> None:
    html = "<html><body><p>Hi</p></body></html>"
    out = inline_css(html, "")
    # Sin reglas CSS premailer no añade nada al <p>; el doc es válido.
    assert "<p" in out


def test_inline_css_returns_raw_on_broken_css(monkeypatch) -> None:
    """Si premailer revienta degrada al HTML sin CSS inlinear."""
    # Forzamos un error inyectando un Premailer fake que rompe.
    import wcm_worker.integrations.html_email as mod

    class BoomPremailer:
        def __init__(self, *args, **kwargs):
            pass

        def transform(self):
            raise RuntimeError("css roto")

    monkeypatch.setattr("premailer.Premailer", BoomPremailer, raising=True)
    out = mod.inline_css("<p>Hi</p>", "p { color: red; }")
    assert "<p>Hi</p>" in out  # no rompe, retorna HTML


# --- html_to_text ---


def test_html_to_text_extracts_paragraphs() -> None:
    text = html_to_text("<p>Hola</p><p>Mundo</p>")
    assert "Hola" in text
    assert "Mundo" in text


def test_html_to_text_preserves_url_in_anchor() -> None:
    """Crítico: la validación legal busca el opt_out_url substring."""
    html = '<p>Click <a href="https://example.com/opt-out?token=x">aquí</a></p>'
    text = html_to_text(html)
    assert "https://example.com/opt-out?token=x" in text
    assert "aquí" in text


def test_html_to_text_strips_scripts_and_styles() -> None:
    html = "<style>p{color:red}</style><script>alert(1)</script><p>Visible</p>"
    text = html_to_text(html)
    assert "Visible" in text
    assert "color" not in text
    assert "alert" not in text


def test_html_to_text_empty_returns_empty() -> None:
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_html_to_text_anchor_without_href_is_just_text() -> None:
    html = "<p>Hola <a>sin href</a> más texto</p>"
    text = html_to_text(html)
    assert "sin href" in text
    assert "(" not in text  # no expandimos URL inexistente
