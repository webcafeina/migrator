"""Carga + composición de la shell HTML maestra de los correos (v0.14.0).

El layout vive en la tabla singleton `email_layouts` (id=1) editable
desde la UI `/settings/email-layout`. El composer y los endpoints de
preview lo cargan vía `load_layout(session)` y lo combinan con el
contenido de la plantilla (slot `{{ content | safe }}`) + CTA + datos
legales + opt-out.

Si la tabla está vacía o no existe (tests, migración no aplicada),
`load_layout` devuelve un layout hardcoded mínimo equivalente al seed
inicial de la migración 0005 — degradación grácil documentada en el
plan v0.14.0.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, StrictUndefined, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from wcm_worker.integrations.html_email import inline_css

log = logging.getLogger("wcm.worker.integrations.email_layout")


@dataclass(frozen=True)
class EmailLayoutSnapshot:
    """Vista inmutable del layout que el composer usa en el render.

    No exponemos el modelo SQLAlchemy directo para no acoplar el
    composer a la session — los endpoints preview también lo construyen
    desde dicts arbitrarios (caso fallback hardcoded).
    """

    layout_html: str
    layout_css: str


# Fallback usado cuando la tabla no existe o está vacía. Refleja lo
# mismo que el seed de la migración 0005 a nivel de funcionalidad
# (referencias a `{{ content }}`, `{{ cta_label/url }}`, `{{ logo_url }}`,
# etc.) pero más compacto — el seed real es la fuente de verdad para
# producción; este es solo para entornos sin migración aplicada.
_FALLBACK_LAYOUT_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"></head>
<body class="wcm-body"><table role="presentation" class="wcm-wrap" width="100%"><tr><td align="center">
<table role="presentation" class="wcm-card" width="600">
<tr><td class="wcm-header">{% if logo_url %}<img src="{{ logo_url }}" alt="Webcafeína" width="160">{% else %}<span class="wcm-brand-text">webcafeína</span>{% endif %}</td></tr>
<tr><td class="wcm-content">{{ content | safe }}
{% if cta_label and cta_url %}<p><a href="{{ cta_url }}" class="wcm-cta">{{ cta_label }} &rarr;</a></p>{% endif %}
</td></tr>
<tr><td class="wcm-footer"><p>{{ company_legal_name }}{% if company_cif %} &middot; CIF {{ company_cif }}{% endif %}{% if company_address %} &middot; {{ company_address }}{% endif %}</p>
<p><a href="mailto:{{ company_contact_email }}">{{ company_contact_email }}</a> &middot;
<a href="{{ privacy_policy_url }}">Política de privacidad</a> &middot;
<a href="{{ opt_out_url }}">Darme de baja</a></p></td></tr>
</table></td></tr></table></body></html>
"""

_FALLBACK_LAYOUT_CSS = """\
.wcm-body { margin:0; background:#f5f6f8; font-family:-apple-system,Helvetica,Arial,sans-serif; color:#1f2937; }
.wcm-wrap { padding:32px 12px; }
.wcm-card { background:#fff; border:1px solid #e5e7eb; border-radius:6px; }
.wcm-header { padding:24px 32px 12px; border-bottom:1px solid #f1f2f4; }
.wcm-content { padding:24px 32px 8px; font-size:15px; line-height:1.6; }
.wcm-content p { margin:0 0 14px; }
.wcm-content a { color:#5a8a00; }
.wcm-footer { padding:16px 32px 24px; border-top:1px solid #f1f2f4; font-size:11.5px; color:#6b7280; }
.wcm-cta { display:inline-block; background:#B1F100; color:#0E1218; padding:10px 18px; border-radius:4px; text-decoration:none; font-weight:700; }
"""


def load_layout(session: Session | None) -> EmailLayoutSnapshot:
    """Devuelve la última versión del layout. Fallback hardcoded si no
    está disponible (BD inalcanzable, tabla aún sin migrar, session
    None en tests).
    """
    if session is None:
        return _fallback()
    try:
        # Import lazy para no acoplar este módulo al modelo durante
        # bootstrap (mismo patrón que el composer con OutreachTemplate).
        from wcm_db.models.outreach import EmailLayout

        stmt = select(EmailLayout).where(EmailLayout.id == 1)
        row = session.execute(stmt).scalar_one_or_none()
    except Exception as e:  # noqa: BLE001 — tabla no existe / BD caída
        log.warning("email_layout_load_failed_fallback", extra={"error": str(e)})
        return _fallback()

    if row is None:
        log.info("email_layout_empty_using_fallback")
        return _fallback()

    return EmailLayoutSnapshot(layout_html=row.layout_html, layout_css=row.layout_css)


def _fallback() -> EmailLayoutSnapshot:
    return EmailLayoutSnapshot(
        layout_html=_FALLBACK_LAYOUT_HTML,
        layout_css=_FALLBACK_LAYOUT_CSS,
    )


def render_full_email(
    layout: EmailLayoutSnapshot,
    *,
    content_html: str,
    subject: str | None,
    cta_label: str | None,
    cta_url: str | None,
    logo_url: str | None,
    template_ctx: dict[str, Any],
) -> str:
    """Renderiza el layout maestro con el contexto completo y aplica
    `inline_css`. Retorna HTML listo para enviar a Resend.

    `template_ctx` debe incluir las variables legales (`company_*`,
    `privacy_policy_url`, `opt_out_url`) — el composer las prepara con
    `_build_template_context` y se las pasa enteras.
    """
    env = Environment(
        autoescape=select_autoescape(default=False, default_for_string=False),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    full_ctx: dict[str, Any] = {
        **template_ctx,
        "content": content_html,
        "subject": subject or "",
        "cta_label": cta_label or "",
        "cta_url": cta_url or "",
        "logo_url": logo_url or "",
    }
    try:
        rendered = env.from_string(layout.layout_html).render(**full_ctx)
    except Exception as e:  # noqa: BLE001 — undefined var o Jinja2 syntax
        log.error(
            "email_layout_render_failed",
            extra={"error": str(e), "layout_chars": len(layout.layout_html)},
        )
        raise

    return inline_css(rendered, layout.layout_css)
