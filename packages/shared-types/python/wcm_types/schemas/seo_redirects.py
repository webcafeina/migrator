from __future__ import annotations

from pydantic import Field

from wcm_types.schemas._base import TimestampedRead, WcmModel


class SeoRedirectRead(TimestampedRead):
    id: int
    project_id: int
    source_path: str = Field(max_length=2048)
    target_path: str = Field(max_length=2048)
    http_status: int
    wp_redirect_id: int | None
