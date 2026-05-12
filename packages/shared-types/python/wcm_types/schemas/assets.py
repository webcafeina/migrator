from __future__ import annotations

from typing import Any

from pydantic import Field, HttpUrl

from wcm_types.enums import AssetStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class AssetBase(WcmModel):
    original_url: HttpUrl
    hash: str = Field(min_length=64, max_length=64)
    mime: str | None = Field(default=None, max_length=80)
    size_bytes: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    alt_text: str | None = None


class AssetCreate(AssetBase):
    project_id: int


class AssetRead(AssetBase, TimestampedRead):
    id: int
    project_id: int
    local_path: str | None
    optimized_path: str | None
    r2_key: str | None
    wp_attachment_id: int | None
    sizes_json: dict[str, Any] | None
    status: AssetStatus
    error_message: str | None
