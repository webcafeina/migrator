"""add outreach_templates table + seed with current .j2 contents

Revision ID: 0003_outreach_templates
Revises: c8e1dc21716b
Create Date: 2026-05-18 18:00:00.000000+00:00

v0.12.0 — migra las plantillas Jinja2 que hasta ahora vivían en disco
(`apps/worker/src/wcm_worker/templates/outreach/*.j2`) a una tabla BD
editable desde el dashboard. El composer mantiene fallback a los `.j2`
si la BD no contiene una plantilla con el nombre solicitado.

El seed inicial INSERTa las 2 plantillas existentes con sus contenidos
hardcoded como strings en este fichero — la migración NO lee
filesystem en runtime para que sea reproducible en entornos donde los
`.j2` puedan haberse eliminado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_outreach_templates"
down_revision: str | None = "c8e1dc21716b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WIX_INTRO_SUBJECT = (
    '{{ business_name | default("Hola") }}, una idea sobre vuestra web '
    "de {{ builder_label }}\n"
)

WIX_INTRO_BODY = """Hola{% if business_name %} {{ business_name }}{% endif %},

Soy {{ sender_name }}, de {{ company_name }}, agencia con base en {{ company_city }}.
Hemos visto que vuestra web actual ({{ website_url }}) está construida en {{ builder_label }}.

Trabajamos con empresas como la vuestra para migrarla a WordPress + Bricks
manteniendo diseño, contenidos y SEO. Suele traducirse en una web más rápida,
con menos coste mensual y mucho margen para crecer (e-commerce, multi-idioma,
integraciones con CRM, etc.).

Si te interesa, te puedo enviar un análisis sin compromiso de vuestra web
actual y una propuesta concreta. Bastan 20 minutos.

Un saludo,
{{ sender_name }}
{{ company_name }} · {{ company_contact_email }}

--
{{ legal_block }}

Si prefieres no recibir más mensajes nuestros, ejerce tu derecho de
oposición aquí (un clic, sin trámites): {{ opt_out_url }}
"""

FOLLOWUP_SUBJECT = 'Re: {{ previous_subject | default("vuestra web") }}\n'

FOLLOWUP_BODY = """Hola{% if business_name %} {{ business_name }}{% endif %},

Te escribía hace unos días con una idea para migrar vuestra web a WordPress.
Si te ha pillado en mal momento, ningún problema — paso por aquí una vez
más para ver si tiene sentido hablar.

Si la respuesta es no, dímelo y no te molesto más. Si prefieres no recibir
ningún email mío nunca, ejerce tu derecho de oposición aquí: {{ opt_out_url }}

Un saludo,
{{ sender_name }}
{{ company_name }} · {{ company_contact_email }}

--
{{ legal_block }}
"""


def upgrade() -> None:
    op.create_table(
        "outreach_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_outreach_templates_name"),
    )

    # Seed con las 2 plantillas existentes. Hardcoded para que sea
    # reproducible (no leemos filesystem desde la migración).
    templates_table = sa.table(
        "outreach_templates",
        sa.column("name", sa.String),
        sa.column("subject_template", sa.Text),
        sa.column("body_template", sa.Text),
        sa.column("language", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.execute(
        sa.insert(templates_table).values(
            [
                {
                    "name": "wix_intro_es",
                    "subject_template": WIX_INTRO_SUBJECT,
                    "body_template": WIX_INTRO_BODY,
                    "language": "es",
                    "created_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
                {
                    "name": "followup_es",
                    "subject_template": FOLLOWUP_SUBJECT,
                    "body_template": FOLLOWUP_BODY,
                    "language": "es",
                    "created_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            ]
        )
    )


def downgrade() -> None:
    op.drop_table("outreach_templates")
