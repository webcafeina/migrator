"""Persistir bricks_global_classes en projects.

Revision ID: 0017_global_classes
Revises: 0016_node_styles
Create Date: 2026-05-21 20:00:00.000000+00:00

Sprint v0.23.0 — bloque C: el transpilador emite globalClasses
deduplicadas a nivel proyecto que el wp_deployer inyectará en la
option `bricks_global_classes` del destino. Persistirlas en
`projects.bricks_global_classes` (JSONB) permite re-ejecutar el deploy
sin re-correr el transpile.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_global_classes"
down_revision: str | None = "0016_node_styles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "bricks_global_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Lista deduplicada de globalClasses emitidas por el "
                "transpiler. Forma: [{id, name, settings}]. "
                "wp_deployer la serializa al option `bricks_global_classes` "
                "del destino."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "bricks_global_classes")
