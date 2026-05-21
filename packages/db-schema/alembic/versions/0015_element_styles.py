"""Element-level styles + residual task screenshots.

Revision ID: 0015_element_styles
Revises: 0014_ai_assist
Create Date: 2026-05-21 19:30:00.000000+00:00

Sprint v0.23.0 — Element-level styling: Bricks editable nativo con fidelidad real.

Cambios:
- `content_blocks.element_styles` (JSONB): computed styles del nodo
  principal del bloque (color, font-size, padding, etc.) capturados por
  `PlaywrightFetcher`. Los mappers Bricks los traducen a settings via
  `_styles_to_bricks_settings` + globalClasses dedup.
- `residual_tasks.section_screenshot_url` (VARCHAR(2048)): URL R2 del
  screenshot de la sección no resuelta. El operador la consulta en el
  checklist para rehacer manualmente.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_element_styles"
down_revision: str | None = "0014_ai_assist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_blocks",
        sa.Column(
            "element_styles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Computed styles del nodo principal capturados por "
                "PlaywrightFetcher. Los mappers los traducen a Bricks "
                "settings."
            ),
        ),
    )
    op.add_column(
        "residual_tasks",
        sa.Column(
            "section_screenshot_url",
            sa.String(length=2048),
            nullable=True,
            comment=(
                "URL R2 del screenshot de la sección no resuelta. "
                "El operador la consulta en el checklist para rehacer "
                "manualmente."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("residual_tasks", "section_screenshot_url")
    op.drop_column("content_blocks", "element_styles")
