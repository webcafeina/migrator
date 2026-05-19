"""Historial de pedidos WooCommerce migrado del back del origen (ADR-045).

PII cifrada con Fernet en la app (billing/shipping address). Borrado
programado tras 30 días por Celery beat (ADR-045 tarea #88).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin


class WooOrder(Base, TimestampMixin):
    __tablename__ = "woo_orders"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_order_id",
            name="uq_woo_orders_project_source_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: ID del pedido en el origen (Wix Stores order_id, Webflow order_id).
    source_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    #: ID del pedido en WC destino. NULL hasta que se migra; rellenado por
    #: WooMigratorAgent extendido (ADR-045 tarea #87).
    wp_order_id: Mapped[int | None] = mapped_column(Integer)
    #: Número de pedido legible (#1024, ORD-XYZ-001).
    order_number: Mapped[str | None] = mapped_column(String(64))
    customer_email: Mapped[str | None] = mapped_column(String(320), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    #: PII — string base64 del Fernet token. Descifrar con
    #: wcm_api.services.source_credentials.decrypt_source_credentials
    #: (o helper específico). NUNCA exponer en ProjectRead/WooOrderRead.
    billing_address_encrypted: Mapped[str | None] = mapped_column(Text)
    shipping_address_encrypted: Mapped[str | None] = mapped_column(Text)
    #: Lista de productos: [{sku, qty, price, total, name}].
    line_items_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    #: Status canónico mapeado: completed | processing | pending | refunded | cancelled.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Dump completo del JSON original del API por si se necesita diagnóstico
    #: o re-migración con mejor mapping. NO exponer en endpoints.
    raw_origin_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    #: Cuándo se migró a WC. NULL = aún no migrado. Para el purge RGPD,
    #: contamos desde este timestamp.
    migrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    migration_error: Mapped[str | None] = mapped_column(Text)
