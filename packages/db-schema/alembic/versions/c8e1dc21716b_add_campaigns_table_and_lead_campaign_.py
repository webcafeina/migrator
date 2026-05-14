"""add campaigns table and lead campaign_id fk

Revision ID: c8e1dc21716b
Revises: 0001
Create Date: 2026-05-14 16:02:16.596576+00:00

Persistir campañas como entidad propia. Antes solo vivían como job
Celery con resultado consultable durante 24h. Se añade en sesión
2026-05-14 para poder mostrar un indicador global multiventana de
campañas en curso.

Limpiado a mano para evitar el ruido de server_default que alembic
autogeneró (los defaults siguen en código y son correctos).
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8e1dc21716b"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=False),
        sa.Column("region", sa.String(length=120), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
                name="campaign_status", native_enum=False, length=32,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_lead_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name=op.f("fk_campaigns_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index(op.f("ix_campaigns_started_at"), "campaigns", ["started_at"])
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"])
    op.create_index(op.f("ix_campaigns_task_id"), "campaigns", ["task_id"], unique=True)

    op.add_column("leads", sa.Column("campaign_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_leads_campaign_id"), "leads", ["campaign_id"])
    op.create_foreign_key(
        op.f("fk_leads_campaign_id_campaigns"),
        "leads", "campaigns", ["campaign_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_leads_campaign_id_campaigns"), "leads", type_="foreignkey"
    )
    op.drop_index(op.f("ix_leads_campaign_id"), table_name="leads")
    op.drop_column("leads", "campaign_id")

    op.drop_index(op.f("ix_campaigns_task_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_status"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_started_at"), table_name="campaigns")
    op.drop_table("campaigns")
