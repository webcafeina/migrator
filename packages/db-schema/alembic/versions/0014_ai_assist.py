"""AI assist phase — section screenshots + content_blocks coverage + ai_section_cache.

Revision ID: 0014_ai_assist
Revises: 0013_qa_reports_ts_default
Create Date: 2026-05-21 12:30:00.000000+00:00

Sprint v0.22.0 — pixel-perfect via Claude vision + RAW fallback.

Cambios:
- `scraped_pages.section_screenshots_json` (JSONB): lista
  `[{idx, selector, url}]` con las URLs R2 de cada sección top-level
  (un screenshot recortado por sección por scraper_origin).
- `content_blocks.section_screenshot_url` (VARCHAR(2048)): la URL del
  screenshot de la sección a la que pertenece el bloque (denormalizado
  para que ai_assist no tenga que hacer join con scraped_pages).
- `content_blocks.coverage_score` (FLOAT): heurística 0-1 que mide
  qué fracción del texto de la sección capturó el extractor. <0.6
  marca el bloque candidato a AI vision.
- `content_blocks.ai_processed` (BOOL, default False): true tras
  ai_assist re-procesar el bloque (independientemente de si quedó
  como AI_GENERATED o RAW_HTML).
- Tabla nueva `ai_section_cache`: cache de respuestas Claude para
  reuso cross-project. Clave = sha256(screenshot + html + selector).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_ai_assist"
down_revision: str | None = "0013_qa_reports_ts_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scraped_pages",
        sa.Column(
            "section_screenshots_json",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )
    op.add_column(
        "content_blocks",
        sa.Column("section_screenshot_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "content_blocks",
        sa.Column("coverage_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "content_blocks",
        sa.Column(
            "ai_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "ai_section_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "response_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("input_hash", name="uq_ai_section_cache_hash"),
    )
    op.create_index(
        "ix_ai_section_cache_input_hash",
        "ai_section_cache",
        ["input_hash"],
        unique=False,
    )
    op.create_index(
        "ix_ai_section_cache_project_id",
        "ai_section_cache",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_section_cache_project_id", table_name="ai_section_cache")
    op.drop_index("ix_ai_section_cache_input_hash", table_name="ai_section_cache")
    op.drop_table("ai_section_cache")
    op.drop_column("content_blocks", "ai_processed")
    op.drop_column("content_blocks", "coverage_score")
    op.drop_column("content_blocks", "section_screenshot_url")
    op.drop_column("scraped_pages", "section_screenshots_json")
