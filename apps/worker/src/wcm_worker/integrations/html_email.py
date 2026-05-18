"""Helpers para el pipeline HTML de los correos de outreach (v0.14.0).

Cuatro utilidades pequeñas, todas puras, sin estado:

- `inline_css(html, css)`: combina `html` + `<style>` con `css` y aplica
  premailer para que las reglas CSS se conviertan en atributos
  `style="…"` inline. Requisito email-safe (Outlook desktop y muchos
  webmails no respetan `<style>` externos). Idempotente y degrada si
  el CSS está roto (retorna el HTML sin inlinear en lugar de romper
  el envío).
- `html_to_text(html)`: extrae texto plano del HTML preservando saltos
  de párrafo + listas + line-breaks. Lo usa el sender para alimentar
  el `text/plain` part del MIME (Resend lo manda en `text=`) y la
  re-validación legal (que opera sobre texto, no markup).
- `wrap_plain_as_html(text)`: convierte texto plano (plantillas legacy
  o steps editados sin formato) en HTML básico — escapa especiales,
  divide en párrafos por dobles saltos, mantiene saltos simples como
  `<br>`. Output válido para inyectar en el slot `{{ content | safe }}`
  del layout maestro.
- `is_html(body)`: heurística — busca tags HTML comunes (no `<` suelto
  para evitar falsos positivos en URLs o emojis).
"""

from __future__ import annotations

import html
import logging
import re

log = logging.getLogger("wcm.worker.integrations.html_email")

# Tags semánticos que un correo de outreach normalmente contiene. Tags
# raros (`<table>` por layout, `<svg>`) NO disparan la detección porque
# nuestro slot de contenido no debería tenerlos (Tiptap los descarta).
_HTML_TAG_RE = re.compile(r"<(p|div|br|a|h[1-6]|ul|ol|li|strong|em|span|b|i)\b", re.IGNORECASE)


def is_html(body: str | None) -> bool:
    """True si el body parece HTML (contiene al menos un tag conocido)."""
    if not body:
        return False
    return bool(_HTML_TAG_RE.search(body))


def wrap_plain_as_html(text: str) -> str:
    """Texto plano → HTML básico. Cada bloque separado por `\\n\\n` es un
    `<p>`; los saltos simples internos se convierten en `<br>`. Escapa
    caracteres HTML especiales del texto original (`<`, `>`, `&`).
    """
    if not text:
        return ""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    paragraphs = []
    for block in blocks:
        escaped = html.escape(block)
        with_breaks = escaped.replace("\n", "<br>\n")
        paragraphs.append(f"<p>{with_breaks}</p>")
    return "\n".join(paragraphs)


def inline_css(html_doc: str, css: str = "") -> str:
    """Inyecta `css` en `<style>` (si no está ya) y aplica premailer.

    Si premailer falla (CSS roto, dependencia caída) loggea warning y
    retorna el HTML original — degradar el correo a "sin inlinear" es
    mejor que romper el envío entero.
    """
    if not html_doc:
        return ""

    full = html_doc
    if css and "<style" not in full.lower():
        # Inyectamos antes de </head> si existe; si no, al principio.
        style_block = f"<style>{css}</style>"
        if "</head>" in full.lower():
            # case-insensitive replace del primer </head>
            full = re.sub(r"</head>", style_block + "</head>", full, count=1, flags=re.IGNORECASE)
        else:
            full = style_block + full

    try:
        from premailer import Premailer

        return Premailer(
            full,
            remove_classes=False,
            keep_style_tags=True,
            disable_validation=True,
            cssutils_logging_level=logging.ERROR,
        ).transform()
    except Exception as e:  # noqa: BLE001 — degradación grácil
        log.warning("premailer_inline_failed_fallback_raw_html", extra={"error": str(e)})
        return full


def html_to_text(html_doc: str | None) -> str:
    """HTML → texto plano legible. Preserva párrafos, line-breaks y
    URLs de los `<a href>` en estilo markdown `texto (url)`.

    Preservar las URLs es crítico para:
    - el `text/plain` part del MIME (clientes sin HTML deben poder
      hacer click al opt-out / website / CTA);
    - la re-validación legal (que comprueba que el `opt_out_url_base`
      aparece literalmente en el body — vive en el layout maestro
      como `<a href>` y sin esta expansión se perdería al pasar a text).

    Usa BeautifulSoup (ya en el stack). Elimina `<script>` y `<style>`
    completos (nunca aparecen en text/plain). Colapsa whitespace
    interno pero mantiene los `\\n\\n` entre bloques.
    """
    if not html_doc:
        return ""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_doc, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Expandir <a href="X">texto</a> → "texto (X)". Si el texto coincide
    # con el href (ej. `<a href="mailto:x">x</a>`), no duplicar.
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        text = a.get_text(strip=True)
        if not href or href == text or href.startswith("#"):
            # Sin URL útil — dejar solo el texto del enlace.
            continue
        a.string = f"{text} ({href})" if text else href

    # Reemplaza <br> por \n y bloques (<p>, <div>, <li>, <h1-6>) por \n\n.
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        block.append("\n\n")

    raw = soup.get_text()
    # Colapsamos espacios redundantes pero respetamos saltos.
    lines = [line.rstrip() for line in raw.split("\n")]
    # Colapsa runs de >2 saltos consecutivos en exactamente 2.
    collapsed: list[str] = []
    empty_run = 0
    for line in lines:
        if not line:
            empty_run += 1
            if empty_run <= 1:
                collapsed.append("")
        else:
            empty_run = 0
            collapsed.append(line)
    return "\n".join(collapsed).strip()
