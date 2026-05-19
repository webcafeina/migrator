"""source credentials encriptadas + preflight cache (onboarding asistido)

Revision ID: 0008_source_creds_preflight
Revises: 0007_visual_diff_qa_reports
Create Date: 2026-05-19 18:00:00.000000+00:00

v0.18.0 — onboarding asistido + acceso al back del origen.
Esta migración agrupa los cambios necesarios para los bloques B+C
del sprint (endpoint preflight + source credentials encriptadas):

1. `projects.source_access_mode` — enum check `none|api|full`. Default
   `none` (modo actual sin acceso al back).
2. `projects.source_credentials_encrypted` — TEXT cifrado con Fernet
   (misma clave que `deploy_credentials_encrypted`). Estructura JSON
   dependiente del builder (WixCredentials, WebflowCredentials, …).
3. `projects.preflight_results_json` — JSONB con resultado del último
   preflight (`{wp_target, plugins, source, source_credentials,
   can_start, blocking_issues, warnings}`).
4. `projects.preflight_at` — TIMESTAMPTZ del último preflight. Cache
   client-side 5 min antes de ejecutar otro.

Downgrade limpio (drop columnas en orden inverso).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0008_source_creds_preflight"
down_revision: str | None = "0007_visual_diff_qa_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "source_access_mode",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
    )
    op.create_check_constraint(
        "ck_projects_source_access_mode",
        "projects",
        "source_access_mode IN ('none', 'api', 'full')",
    )
    op.add_column(
        "projects",
        sa.Column("source_credentials_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "preflight_results_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column("preflight_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "preflight_at")
    op.drop_column("projects", "preflight_results_json")
    op.drop_column("projects", "source_credentials_encrypted")
    op.drop_constraint("ck_projects_source_access_mode", "projects", type_="check")
    op.drop_column("projects", "source_access_mode")
