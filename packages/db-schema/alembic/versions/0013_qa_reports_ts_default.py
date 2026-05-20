"""TimestampMixin: añadir server_default now() faltante en 5 tablas

Revision ID: 0013_qa_reports_ts_default
Revises: 0012_max_pages_scrape
Create Date: 2026-05-20 11:30:00.000000+00:00

Bug histórico: varias migraciones (0007 visual_diff_qa_reports, 0011
woo_orders, las de email_layouts y outreach_templates) declararon
`created_at`/`updated_at` como `NOT NULL` pero **sin server_default**.
SQLAlchemy con TimestampMixin no enviaba valor → Postgres rechazaba
con NotNullViolation al hacer INSERT.

Detectado en la primera prueba E2E con mariya.design (2026-05-20):
qa_runner reventó al persistir QaReport por el bug del server_default
en qa_reports. Auditoría posterior reveló que el mismo bug afecta a:
- qa_reports
- visual_diffs
- woo_orders
- email_layouts
- outreach_templates

Otras tablas TimestampMixin (scraped_pages, projects, leads, etc.) ya
tienen `now()` correcto. Esta migración uniformiza las 5 restantes.

Defensa en profundidad: el TimestampMixin también recibe un `default`
Python (`datetime.now(UTC)`) para que SQLAlchemy nunca envíe NULL aunque
una BD nueva olvide el server_default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_qa_reports_ts_default"
down_revision: str | None = "0012_max_pages_scrape"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AFFECTED_TABLES = (
    "qa_reports",
    "visual_diffs",
    "woo_orders",
    "email_layouts",
    "outreach_templates",
)


def upgrade() -> None:
    for table in AFFECTED_TABLES:
        for col in ("created_at", "updated_at"):
            op.alter_column(
                table,
                col,
                server_default=sa.text("now()"),
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
            )


def downgrade() -> None:
    for table in AFFECTED_TABLES:
        for col in ("created_at", "updated_at"):
            op.alter_column(
                table,
                col,
                server_default=None,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
            )
