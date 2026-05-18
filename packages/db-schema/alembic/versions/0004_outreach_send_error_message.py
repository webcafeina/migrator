"""add error_message to outreach_sends

Revision ID: 0004_outreach_send_error_message
Revises: 0003_outreach_templates
Create Date: 2026-05-18 19:00:00.000000+00:00

v0.13.2 — el operador no veía por qué un envío fallaba: el sender
marcaba FAILED pero la excepción rollbackeaba la BD y el send quedaba
QUEUED indefinidamente. Tras el fix del agent (commit antes del
raise), añadimos campo `error_message` para que el operador vea el
motivo del fallo desde la UI sin SSHear al servidor.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_outreach_send_error_message"
down_revision: str | None = "0003_outreach_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outreach_sends",
        sa.Column("error_message", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_sends", "error_message")
