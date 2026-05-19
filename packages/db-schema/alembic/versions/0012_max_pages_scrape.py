"""cap max_pages configurable por proyecto en scrape_origin (ADR-050)

Revision ID: 0012_max_pages_scrape
Revises: 0011_woo_orders
Create Date: 2026-05-19 19:33:00.000000+00:00

v0.20.0 — añade `projects.max_pages_scrape INT NULL`. Cascada: NULL =
usa env SCRAPE_MAX_PAGES_DEFAULT (default 50). Rango válido 1-500.

Backward compat: proyectos pre-v0.20.0 tienen NULL → default 50
preservado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_max_pages_scrape"
down_revision: str | None = "0011_woo_orders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("max_pages_scrape", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_projects_max_pages_scrape_range",
        "projects",
        "max_pages_scrape IS NULL OR (max_pages_scrape >= 1 AND max_pages_scrape <= 500)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_projects_max_pages_scrape_range", "projects", type_="check"
    )
    op.drop_column("projects", "max_pages_scrape")
