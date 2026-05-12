from __future__ import annotations

from typing import Any

from pydantic import Field

from wcm_types.enums import BlockType, ContentBlockSource
from wcm_types.schemas._base import TimestampedRead, WcmModel


class ContentBlockBase(WcmModel):
    block_type: BlockType
    order_index: int = Field(ge=0)
    lang: str | None = Field(default=None, max_length=8)
    content_json: dict[str, Any] = Field(default_factory=dict)
    source: ContentBlockSource = ContentBlockSource.EXTRACTED


class ContentBlockCreate(ContentBlockBase):
    project_id: int
    page_id: int


class ContentBlockRead(ContentBlockBase, TimestampedRead):
    id: int
    project_id: int
    page_id: int
