"""pre-deploy snapshot SQL del WP destino para rollback robusto (ADR-042)

Revision ID: 0009_pre_deploy_snapshot
Revises: 0008_source_creds_preflight
Create Date: 2026-05-19 19:30:00.000000+00:00

v0.20.0 — añade 2 cols a `projects` para soportar el agente
`pre_deploy_snapshot` que ejecuta `wp db export` vía SSH antes de
`wp-deployer`. El `RollbackAgent` extendido (ADR-042) usa el snapshot
para `wp db import` (restore atómico) si está disponible; fallback al
MVP (DELETE páginas por wp_post_id) si NULL.

Sin breaking: proyectos pre-v0.20.0 tienen NULL → comportamiento MVP
preservado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_pre_deploy_snapshot"
down_revision: str | None = "0008_source_creds_preflight"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("pre_deploy_snapshot_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("pre_deploy_snapshot_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "pre_deploy_snapshot_at")
    op.drop_column("projects", "pre_deploy_snapshot_path")
