"""add html template + cta cols + email_layouts singleton + body_html_rendered

Revision ID: 0005_email_html_layout
Revises: 0004_outreach_send_error_message
Create Date: 2026-05-18 22:00:00.000000+00:00

v0.14.0 — pipeline HTML estilado para los correos de outreach. Hasta
ahora el composer renderizaba la plantilla Jinja2 a texto plano y el
sender lo enviaba sin formato. Esta migración prepara la capa de datos
para el pipeline HTML completo:

1. `outreach_templates` gana 3 columnas opcionales: `body_html_template`
   (Jinja2 HTML — si NULL, el composer cae a `body_template` texto y lo
   envuelve en `<p>`), `cta_label` y `cta_url` (botón CTA opcional
   pintado por el layout).
2. `outreach_sends` gana `body_html_rendered` (snapshot del HTML
   enviado, NULL para sends históricos pre-v0.14.0; el preview endpoint
   re-renderiza on-the-fly en ese caso).
3. Nueva tabla singleton `email_layouts` con la shell HTML maestra
   editable desde `/settings/email-layout`. `CHECK (id = 1)` fuerza el
   invariante. Seed con un layout inicial email-safe (tabla 600px,
   header logo, slot, CTA condicional, footer legal).

NO se hace backfill de `body_html_template` en plantillas existentes
(quedan NULL → composer fallback). El operador puede migrar las 2
plantillas seed a HTML editándolas desde la nueva UI WYSIWYG.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_email_html_layout"
down_revision: str | None = "0004_outreach_send_error_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Layout HTML inicial — email-safe (tabla 600px max, sin flexbox). El
# CSS embebido en `<style>` lo inlinea premailer en runtime. Variables
# Jinja2 inyectadas por el composer al renderizar:
#   - {{ logo_url }} → header (puede ser vacío → fallback texto)
#   - {{ content }} → slot del cuerpo de la plantilla
#   - {{ cta_label }} / {{ cta_url }} → botón opcional
#   - {{ company_legal_name }}, {{ company_cif }}, {{ company_address }},
#     {{ company_contact_email }} → firma legal LSSI
#   - {{ privacy_policy_url }}, {{ opt_out_url }} → cumplimiento RGPD
INITIAL_LAYOUT_HTML = """<!doctype html>
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
      <table role="presentation" class="wcm-card" cellpadding="0" cellspacing="0" border="0" width="600">
        <tr>
          <td class="wcm-header">
            {% if logo_url %}
              <img src="{{ logo_url }}" alt="Webcafeína" width="160" class="wcm-logo">
            {% else %}
              <span class="wcm-brand-text">webcafe<span class="wcm-brand-accent">í</span>na</span>
            {% endif %}
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
              {{ company_legal_name }}{% if company_cif %} &middot; CIF {{ company_cif }}{% endif %}
              {% if company_address %}&middot; {{ company_address }}{% endif %}
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
"""

INITIAL_LAYOUT_CSS = """\
.wcm-body { margin: 0; padding: 0; background-color: #f5f6f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; }
.wcm-wrap { background-color: #f5f6f8; padding: 32px 12px; }
.wcm-card { background-color: #ffffff; border-radius: 6px; border: 1px solid #e5e7eb; }
.wcm-header { padding: 28px 32px 16px 32px; border-bottom: 1px solid #f1f2f4; }
.wcm-logo { display: block; height: auto; max-width: 160px; }
.wcm-brand-text { font-size: 22px; font-weight: 700; letter-spacing: -0.01em; color: #0E1218; }
.wcm-brand-accent { color: #5a8a00; }
.wcm-content { padding: 28px 32px 8px 32px; font-size: 15px; line-height: 1.65; color: #1f2937; }
.wcm-content p { margin: 0 0 14px 0; }
.wcm-content a { color: #5a8a00; text-decoration: underline; }
.wcm-content strong { font-weight: 600; color: #0E1218; }
.wcm-content ul, .wcm-content ol { margin: 0 0 14px 22px; padding: 0; }
.wcm-content li { margin: 0 0 4px 0; }
.wcm-cta-wrap { margin: 8px 0 18px 0; }
.wcm-cta { display: inline-block; background-color: #B1F100; color: #0E1218; text-decoration: none; font-weight: 700; font-size: 14px; padding: 12px 20px; border-radius: 4px; border: 1px solid #94c800; }
.wcm-footer { padding: 18px 32px 28px 32px; border-top: 1px solid #f1f2f4; }
.wcm-footer-line { margin: 4px 0; font-size: 11.5px; line-height: 1.5; color: #6b7280; }
.wcm-footer-link { color: #6b7280; text-decoration: underline; }
"""


def upgrade() -> None:
    # 1. outreach_templates — body_html_template + cta_*
    op.add_column(
        "outreach_templates",
        sa.Column("body_html_template", sa.Text(), nullable=True),
    )
    op.add_column(
        "outreach_templates",
        sa.Column("cta_label", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "outreach_templates",
        sa.Column("cta_url", sa.String(length=500), nullable=True),
    )

    # 2. outreach_sends — body_html_rendered (snapshot histórico)
    op.add_column(
        "outreach_sends",
        sa.Column("body_html_rendered", sa.Text(), nullable=True),
    )

    # 3. email_layouts — singleton con CHECK (id = 1)
    op.create_table(
        "email_layouts",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("layout_html", sa.Text(), nullable=False),
        sa.Column(
            "layout_css",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_email_layouts_updated_by_user_id_users",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_email_layouts"),
        sa.CheckConstraint("id = 1", name="ck_email_layouts_singleton"),
    )

    # Seed con el layout inicial.
    layouts_table = sa.table(
        "email_layouts",
        sa.column("id", sa.Integer),
        sa.column("layout_html", sa.Text),
        sa.column("layout_css", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.insert(layouts_table).values(
            [
                {
                    "id": 1,
                    "layout_html": INITIAL_LAYOUT_HTML,
                    "layout_css": INITIAL_LAYOUT_CSS,
                    "created_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                }
            ]
        )
    )


def downgrade() -> None:
    op.drop_table("email_layouts")
    op.drop_column("outreach_sends", "body_html_rendered")
    op.drop_column("outreach_templates", "cta_url")
    op.drop_column("outreach_templates", "cta_label")
    op.drop_column("outreach_templates", "body_html_template")
