"""Productos WooCommerce detectados o migrados."""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin


class WooProduct(Base, TimestampMixin):
    __tablename__ = "woo_products"
    __table_args__ = (
        UniqueConstraint("project_id", "sku", name="uq_woo_products_project_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(String(80))  # id en origen (Wix Stores, Webflow Ecom, etc.)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    stock: Mapped[int | None] = mapped_column(Integer)
    stock_managed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    attributes_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    variations_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    image_asset_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    wp_product_id: Mapped[int | None] = mapped_column(Integer, index=True)
