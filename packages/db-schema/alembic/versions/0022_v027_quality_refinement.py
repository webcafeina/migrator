"""Image quality scoring + Brief refinement proposals (v0.27.0).

Revision ID: 0022_v027_quality_refinement
Revises: 0021_v026_hybrid_images
Create Date: 2026-05-22 21:00:00.000000+00:00

Sprint v0.27.0 — Detección automática de imágenes feas + Brief
refinement iterativo con AI.

Cambios:
- `assets.quality_score` (Numeric(3,2)): rango 0.00-1.00. Calculada
  por heurística determinista en AssetOptimizerAgent. NULL = no
  analizada todavía (assets legacy v0.26.0 y anteriores).
- `assets.quality_flags_json` (JSONB): lista de strings
  (`low_resolution`, `obsolete_format`, `weird_aspect_ratio`, etc.)
  para que el dashboard muestre tooltip explicativo del badge.
- `projects.brief_refinement_proposals_json` (JSONB): última batch
  de propuestas generadas por BriefRefinementAgent. Shape:
  `{generated_at, model, cost_usd, proposals: [...]}`. Persistencia
  permite auditoría + idempotencia + caching ligero.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_v027_quality_refinement"
down_revision: str | None = "0021_v026_hybrid_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column(
            "quality_score",
            sa.Numeric(precision=3, scale=2),
            nullable=True,
            comment=(
                "Score 0.00-1.00 calculado por heurística "
                "image_quality. <0.50 = candidato a regenerar con AI."
            ),
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "quality_flags_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Lista de flags (low_resolution, obsolete_format, etc.) "
                "para tooltip explicativo en /preview."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "brief_refinement_proposals_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Última batch de propuestas del BriefRefinementAgent: "
                "{generated_at, model, cost_usd, proposals: [...]}"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "brief_refinement_proposals_json")
    op.drop_column("assets", "quality_flags_json")
    op.drop_column("assets", "quality_score")
