"""Brief fields para pivote arquitectónico v0.25.0.

Revision ID: 0020_brief_fields
Revises: 0019_project_wp_menu
Create Date: 2026-05-22 14:00:00.000000+00:00

Sprint v0.25.0 — Pivote arquitectónico de "replicar fielmente origen"
a "rediseño desde info del origen". Introduce el contrato canónico
`Brief` JSON intermedio que alimenta los dos pipelines de output:
Templates Bricks (brickstemplate.com curado) o AI (OpenAI gpt-4o).

Cambios:
- `projects.business_description` (TEXT): auto-detectado por OpenAI
  gpt-4o-mini + editable en wizard.
- `projects.business_sector` (VARCHAR(80)): restaurant/agency/etc.
- `projects.target_audience` (TEXT).
- `projects.tone_of_voice` (VARCHAR(20)): formal/casual/friendly/etc.
- `projects.usps_json` (JSONB): lista de 3-5 strings.
- `projects.design_method` (VARCHAR(20)): templates/ai. NULL para
  proyectos legacy (v0.24.0 y anteriores).
- `projects.brief_json` (JSONB): Brief canónico generado por
  BriefGenerator. Shape: business + brand + navigation + footer + pages[].
- `projects.design_proposals_json` (JSONB): metadatos del pipeline de
  diseño (templates seleccionados por sección, prompt AI, etc.) para
  edición iterativa.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_brief_fields"
down_revision: str | None = "0019_project_wp_menu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "business_description",
            sa.Text(),
            nullable=True,
            comment=(
                "Descripción libre 2-5 líneas del negocio. "
                "Auto-detectada por OpenAI gpt-4o-mini + editable."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("business_sector", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("target_audience", sa.Text(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "tone_of_voice",
            sa.String(length=20),
            nullable=True,
            comment=(
                "Enum sugerido en form: "
                "formal/casual/friendly/premium/playful/serious."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "usps_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="3-5 unique selling points como lista de strings.",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "design_method",
            sa.String(length=20),
            nullable=True,
            comment=(
                "Pipeline de generación: `templates` (Brickstemplate.com) "
                "o `ai` (OpenAI gpt-4o). NULL = legacy proyecto v0.24.0."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "brief_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Brief canónico generado por BriefGenerator. "
                "Contrato único: business + brand + navigation + "
                "footer + pages[]."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "design_proposals_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Metadatos del pipeline de diseño (templates por sección, "
                "prompt AI, thumbnails). Para edición iterativa."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "design_proposals_json")
    op.drop_column("projects", "brief_json")
    op.drop_column("projects", "design_method")
    op.drop_column("projects", "usps_json")
    op.drop_column("projects", "tone_of_voice")
    op.drop_column("projects", "target_audience")
    op.drop_column("projects", "business_sector")
    op.drop_column("projects", "business_description")
