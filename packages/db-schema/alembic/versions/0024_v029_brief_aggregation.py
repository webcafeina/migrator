"""Brief aggregation cache + cost telemetry (v0.29.0 B0).

Revision ID: 0024_v029_brief_aggregation
Revises: 0023_v028_template_choices_cache
Create Date: 2026-06-03 10:00:00.000000+00:00

Sprint v0.29.0 — `BriefSectionAggregator` reagrupa los bloques planos del
`ContentExtractor` en secciones semánticas que matcheen el catálogo
brickstemplate. Dos columnas nuevas en `projects`:

- `brief_aggregation_cache_json` (JSONB): mapa `{page_blocks_sha:
  {sections: [...], model, cost_usd, generated_at}}` para idempotencia
  entre re-runs del pipeline. Si el SHA256 de los bloques de una página
  no ha cambiado entre dos invocaciones, se reutiliza el agregado.
- `brief_aggregation_cost_usd` (Numeric 8,4): coste acumulado total del
  agregador para el proyecto. Usado por el wizard para el modal de
  confirmación (>20 páginas → muestra coste estimado al operador).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_v029_brief_aggregation"
down_revision: str | None = "0023_v028_template_choices_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "brief_aggregation_cache_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Cache del BriefSectionAggregator (v0.29.0). Shape: "
                "{page_blocks_sha: {sections, model, cost_usd, generated_at}}. "
                "Permite idempotencia entre re-runs sin re-llamar al LLM."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "brief_aggregation_cost_usd",
            sa.Numeric(precision=8, scale=4),
            nullable=False,
            server_default=sa.text("'0.0000'"),
            comment=(
                "Coste acumulado USD del BriefSectionAggregator en este "
                "proyecto. Usado por el wizard para mostrar coste real."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "brief_aggregation_cost_usd")
    op.drop_column("projects", "brief_aggregation_cache_json")
