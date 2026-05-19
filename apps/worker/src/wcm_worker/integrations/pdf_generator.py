"""Generador de PDF con WeasyPrint (v0.16.0).

Pipeline: Markdown → HTML (`markdown-it-py`) → PDF (`WeasyPrint`).
Manteniendo la fuente de verdad en Markdown:
- Es legible/diffable en code review.
- Sirve también como entregable .md al cliente.
- Conversión MD→HTML→PDF garantiza consistencia visual entre formatos.

WeasyPrint requiere dependencias del SO (libpango, libcairo,
libgdk-pixbuf). En macOS dev: viene con brew. En Linux server:
`apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0`.

Si WeasyPrint falla por dependencias missing, `render_pdf` devuelve
`b""` (bytes vacío) + log warning. El agent caller decide si genera
solo el MD (residual task "instalar WeasyPrint en server").
"""

from __future__ import annotations

import logging

log = logging.getLogger("wcm.worker.integrations.pdf_generator")


class WeasyPrintNotAvailableError(RuntimeError):
    """WeasyPrint no se puede importar (deps SO faltantes)."""


def render_markdown_to_html(md: str) -> str:
    """Convierte markdown a HTML con markdown-it-py (CommonMark spec).

    Output es HTML válido sin `<html>/<body>` wrapper — el caller
    encadena con la plantilla full-page que tiene `<style>` y `<body>`.
    """
    from markdown_it import MarkdownIt

    md_engine = MarkdownIt("commonmark", {"html": False, "linkify": True})
    return md_engine.render(md)


def render_pdf(html: str, css: str = "") -> bytes:
    """HTML + CSS → PDF bytes con WeasyPrint.

    Si WeasyPrint no está disponible (deps SO faltantes), devuelve
    bytes vacío + log warning. El caller decide qué hacer (residual
    task con instrucciones de instalación + degrada a solo MD).
    """
    try:
        from weasyprint import CSS, HTML
    except ImportError as e:
        log.warning("weasyprint_not_available", extra={"error": str(e)})
        return b""
    except OSError as e:
        # WeasyPrint importa cairo/pango al hacer `from weasyprint`.
        # Si falta una lib del SO, OSError aquí.
        log.warning("weasyprint_deps_missing", extra={"error": str(e)})
        return b""

    try:
        pdf_doc = HTML(string=html).render(
            stylesheets=[CSS(string=css)] if css else None,
        )
        return pdf_doc.write_pdf()
    except Exception as e:  # noqa: BLE001 — WeasyPrint puede lanzar varios
        log.warning("weasyprint_render_failed", extra={"error": str(e)})
        return b""


def weasyprint_available() -> bool:
    """True si WeasyPrint se puede importar sin errores (deps SO OK)."""
    try:
        import weasyprint  # noqa: F401

        return True
    except (ImportError, OSError):
        return False
