"""visual_diff threshold configurable por proyecto (ADR-044)

Revision ID: 0010_visual_diff_threshold
Revises: 0009_pre_deploy_snapshot
Create Date: 2026-05-19 19:31:00.000000+00:00

v0.20.0 — añade `projects.visual_diff_threshold FLOAT NULL`. Cascada:
NULL = usa env VISUAL_DIFF_RESIDUAL_THRESHOLD (default 0.70). Rango
válido 0-1, validado vía CHECK constraint.

Backward compat: proyectos pre-v0.20.0 tienen NULL → comportamiento
con default global preservado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010_visual_diff_threshold"
down_revision: str | None = "0009_pre_deploy_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("visual_diff_threshold", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        "ck_projects_visual_diff_threshold_range",
        "projects",
        "visual_diff_threshold IS NULL OR (visual_diff_threshold >= 0 AND visual_diff_threshold <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_projects_visual_diff_threshold_range", "projects", type_="check"
    )
    op.drop_column("projects", "visual_diff_threshold")
