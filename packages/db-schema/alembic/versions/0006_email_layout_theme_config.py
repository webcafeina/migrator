"""add theme_config jsonb to email_layouts

Revision ID: 0006_email_layout_theme_config
Revises: 0005_email_html_layout
Create Date: 2026-05-19 10:00:00.000000+00:00

v0.15.0 — editor visual del layout maestro. Cuando el operador edita
desde el tab "Visual" de `/settings/email-layout`, el form construye
un `EmailLayoutTheme` JSON y el backend regenera `layout_html` +
`layout_css` desde la plantilla canónica. Persistimos el JSON para
poder volver a hidratar el form al re-abrirlo (sin re-parsear HTML).

El singleton existente (id=1, seedeado en migración 0005) NO recibe
backfill aquí — queda con `theme_config=NULL` y el frontend lo trata
como "modo Código". El operador puede pulsar "Reset al tema por
defecto" para activar el modo Visual con los defaults.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_email_layout_theme_config"
down_revision: str | None = "0005_email_html_layout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_layouts",
        sa.Column(
            "theme_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("email_layouts", "theme_config")
