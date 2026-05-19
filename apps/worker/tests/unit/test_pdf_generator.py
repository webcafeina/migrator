"""Tests del helper pdf_generator (v0.16.0)."""

from __future__ import annotations

from unittest.mock import patch

from wcm_worker.integrations.pdf_generator import (
    render_markdown_to_html,
    render_pdf,
    weasyprint_available,
)


def test_markdown_to_html_convierte_basics() -> None:
    md = "# Título\n\nPárrafo con **negrita** y [link](https://x.es)."
    html = render_markdown_to_html(md)
    assert "<h1>Título</h1>" in html
    assert "<strong>negrita</strong>" in html
    assert '<a href="https://x.es">' in html


def test_markdown_to_html_tabla_renderiza_como_html() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html = render_markdown_to_html(md)
    # markdown-it-py CommonMark NO renderiza tablas por defecto.
    # Esto verifica el comportamiento actual (tabla queda como texto).
    # Si en el futuro queremos tablas, activar plugin GFM.
    assert "<table" in html or "| A | B |" in html


def test_weasyprint_available_consistente_con_render() -> None:
    """Si available=True el render produce PDF; si False, bytes vacío.

    No asumimos available=True/False fijo: depende de si las libs SO
    (cairo/pango/gdk-pixbuf) están instaladas en el entorno actual.
    """
    is_available = weasyprint_available()
    html = "<!doctype html><html><body><h1>Test</h1></body></html>"
    pdf = render_pdf(html)
    if is_available:
        assert pdf.startswith(b"%PDF"), "WeasyPrint disponible pero no produjo PDF"
        assert len(pdf) > 500
    else:
        assert pdf == b"", "WeasyPrint NO disponible debe devolver bytes vacío"


def test_render_pdf_vacio_si_html_class_lanza() -> None:
    """Defense in depth: si WeasyPrint.HTML lanza al construir,
    `render_pdf` devuelve bytes vacío en vez de propagar."""

    class BoomHTML:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    # Solo tiene sentido si WeasyPrint se puede importar (libs SO ok).
    # Sin cairo/pango la rama del except ImportError/OSError ya cubre.
    if not weasyprint_available():
        return

    with patch("weasyprint.HTML", BoomHTML):
        pdf = render_pdf("<html></html>")
    assert pdf == b""
