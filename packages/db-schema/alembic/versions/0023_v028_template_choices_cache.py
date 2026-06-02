"""Template choices cache (v0.28.0 B14).

Revision ID: 0023_v028_template_choices_cache
Revises: 0022_v027_quality_refinement
Create Date: 2026-06-02 12:00:00.000000+00:00

Sprint v0.28.0 — Cache de elecciones del LLMSectionRanker (templates
brickstemplate) para idempotencia entre re-runs del pipeline.

Cambios:
- `projects.template_choices_cache_json` (JSONB): mapa
  `{cache_key: {template_id, rationale, model, cached_at}}` donde
  cache_key es `f"{section_index}:{candidates_sha[:8]}"`. Si el
  pipeline re-corre con los mismos candidatos para la misma sección,
  se reutiliza la elección y no se vuelve a llamar al LLM.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_v028_template_choices_cache"
down_revision: str | None = "0022_v027_quality_refinement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "template_choices_cache_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Cache de elecciones del LLMSectionRanker. Shape: "
                "{cache_key: {template_id, rationale, model, cached_at}}. "
                "cache_key = f'{section_index}:{candidates_sha[:8]}'."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "template_choices_cache_json")
