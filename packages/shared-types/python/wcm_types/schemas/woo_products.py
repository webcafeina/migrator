from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import Field

from wcm_types.schemas._base import TimestampedRead, WcmModel


class WooProductRead(TimestampedRead):
    id: int
    project_id: int
    source_id: str | None
    sku: str = Field(max_length=80)
    name: str = Field(max_length=512)
    price: Decimal | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    stock: int | None = None
    stock_managed: bool
    attributes_json: list[dict[str, Any]] | None
    variations_json: list[dict[str, Any]] | None
    image_asset_ids: list[int]
    categories: list[str]
    wp_product_id: int | None
