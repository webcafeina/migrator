"""visual_diffs + qa_reports + checklist URLs (cierre flujo migración)

Revision ID: 0007_visual_diff_qa_reports
Revises: 0006_email_layout_theme_config
Create Date: 2026-05-19 14:00:00.000000+00:00

v0.16.0 — cierre del flujo de migración con los 3 stubs transversales
(visual-diff + qa-runner + checklist-generator) pasando a implementación
real. Esta migración agrupa los 3 cambios de BD para evitar
migraciones consecutivas sin valor independiente:

1. `visual_diffs` (nueva): comparaciones página-a-página origen vs
   destino. Una fila por (project_id, page_path) — UPSERT en
   re-ejecución del agent.
2. `qa_reports` (nueva): histórico de reportes Lighthouse + W3C +
   broken links + checks binarios. Una fila por ejecución del agent.
3. `projects.checklist_md_url` + `projects.checklist_pdf_url`: URLs
   R2 del entregable final del proyecto.

Downgrade limpio (drop en orden inverso).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_visual_diff_qa_reports"
down_revision: str | None = "0006_email_layout_theme_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. visual_diffs — comparaciones por página.
    op.create_table(
        "visual_diffs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "projects.id",
                ondelete="CASCADE",
                name="fk_visual_diffs_project_id_projects",
            ),
            nullable=False,
        ),
        sa.Column("page_path", sa.String(length=2048), nullable=False),
        sa.Column("source_screenshot_url", sa.String(length=1024), nullable=True),
        sa.Column("target_screenshot_url", sa.String(length=1024), nullable=True),
        sa.Column("overlay_url", sa.String(length=1024), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("viewport_width", sa.Integer(), nullable=False, server_default="1280"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_visual_diffs"),
        sa.UniqueConstraint("project_id", "page_path", name="uq_visual_diffs_project_page"),
    )
    op.create_index("ix_visual_diffs_project_id", "visual_diffs", ["project_id"])

    # 2. qa_reports — reportes QA post-deploy.
    op.create_table(
        "qa_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "projects.id",
                ondelete="CASCADE",
                name="fk_qa_reports_project_id_projects",
            ),
            nullable=False,
        ),
        sa.Column("lighthouse_perf_desktop", sa.SmallInteger(), nullable=True),
        sa.Column("lighthouse_perf_mobile", sa.SmallInteger(), nullable=True),
        sa.Column("lighthouse_a11y_avg", sa.SmallInteger(), nullable=True),
        sa.Column("lighthouse_best_practices_avg", sa.SmallInteger(), nullable=True),
        sa.Column("lighthouse_seo_avg", sa.SmallInteger(), nullable=True),
        sa.Column(
            "html_validator_errors_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "html_validator_warnings_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("broken_links_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_links_checked",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("https_valid", sa.Boolean(), nullable=True),
        sa.Column("robots_accessible", sa.Boolean(), nullable=True),
        sa.Column("sitemap_accessible", sa.Boolean(), nullable=True),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_qa_reports"),
    )
    op.create_index("ix_qa_reports_project_id", "qa_reports", ["project_id"])

    # 3. projects — checklist URLs.
    op.add_column(
        "projects",
        sa.Column("checklist_md_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("checklist_pdf_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "checklist_pdf_url")
    op.drop_column("projects", "checklist_md_url")
    op.drop_index("ix_qa_reports_project_id", table_name="qa_reports")
    op.drop_table("qa_reports")
    op.drop_index("ix_visual_diffs_project_id", table_name="visual_diffs")
    op.drop_table("visual_diffs")
