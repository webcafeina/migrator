"""Hybrid per-section + image generation budget + preview thumbnails (v0.26.0).

Revision ID: 0021_v026_hybrid_images
Revises: 0020_brief_fields
Create Date: 2026-05-22 17:00:00.000000+00:00

Sprint v0.26.0 — Hybrid per-section + image generation + preview thumbnails.

Cambios:
- `projects.image_generation_budget_usd` (Numeric(6,2), default 1.00):
  límite duro de gasto en gpt-image-2 por proyecto. Si se supera, el
  agente para + crea ResidualTask con los slots no rellenos.
- `bricks_pages.preview_thumbnail_url` (VARCHAR(500)): URL R2 del
  thumbnail Playwright sobre el draft WP del proyecto.
- `bricks_pages.preview_captured_at` (TIMESTAMP): para cache
  invalidation. Si bricks_json cambia después del thumbnail, regenerar.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_v026_hybrid_images"
down_revision: str | None = "0020_brief_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "image_generation_budget_usd",
            sa.Numeric(precision=6, scale=2),
            nullable=True,
            server_default="1.00",
            comment=(
                "Límite duro de gasto en gpt-image-2 por proyecto. "
                "Si se supera, el agente para + ResidualTask."
            ),
        ),
    )
    op.add_column(
        "bricks_pages",
        sa.Column(
            "preview_thumbnail_url",
            sa.String(length=500),
            nullable=True,
            comment="URL R2 del thumbnail Playwright sobre el draft WP.",
        ),
    )
    op.add_column(
        "bricks_pages",
        sa.Column(
            "preview_captured_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp de la última captura. "
                "Si bricks_json cambia después, regenerar."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("bricks_pages", "preview_captured_at")
    op.drop_column("bricks_pages", "preview_thumbnail_url")
    op.drop_column("projects", "image_generation_budget_usd")
