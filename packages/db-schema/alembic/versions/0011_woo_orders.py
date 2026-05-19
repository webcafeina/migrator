"""tabla woo_orders con PII cifrada para historial pedidos (ADR-045)

Revision ID: 0011_woo_orders
Revises: 0010_visual_diff_threshold
Create Date: 2026-05-19 19:32:00.000000+00:00

v0.20.0 — nueva tabla `woo_orders` que persiste el historial de
pedidos migrado desde el back del origen (Wix Stores / Webflow
Ecommerce) cuando hay credenciales API válidas.

PII cifrada con Fernet en la app (billing_address_json,
shipping_address_json). Borrado programado tras 30 días (Celery beat
configurable via WOO_ORDERS_RETENTION_DAYS).

Sin breaking: tabla nueva, no afecta proyectos existentes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011_woo_orders"
down_revision: str | None = "0010_visual_diff_threshold"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "woo_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_order_id", sa.String(length=128), nullable=False),
        sa.Column("wp_order_id", sa.Integer(), nullable=True),
        sa.Column("order_number", sa.String(length=64), nullable=True),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        # PII cifrada en aplicación con Fernet (NO cifrada a nivel BD).
        # Almacenada como TEXT base64 del Fernet token.
        sa.Column("billing_address_encrypted", sa.Text(), nullable=True),
        sa.Column("shipping_address_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "line_items_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "raw_origin_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("migrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("migration_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_woo_orders_project",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_woo_orders"),
        sa.UniqueConstraint(
            "project_id", "source_order_id",
            name="uq_woo_orders_project_source_order",
        ),
    )
    op.create_index("ix_woo_orders_project_id", "woo_orders", ["project_id"])
    op.create_index("ix_woo_orders_customer_email", "woo_orders", ["customer_email"])
    op.create_index("ix_woo_orders_migrated_at", "woo_orders", ["migrated_at"])


def downgrade() -> None:
    op.drop_index("ix_woo_orders_migrated_at", table_name="woo_orders")
    op.drop_index("ix_woo_orders_customer_email", table_name="woo_orders")
    op.drop_index("ix_woo_orders_project_id", table_name="woo_orders")
    op.drop_table("woo_orders")
