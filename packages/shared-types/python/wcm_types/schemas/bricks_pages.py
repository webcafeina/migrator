from __future__ import annotations

from typing import Any

from pydantic import Field

from wcm_types.enums import ScrapeStatus
from wcm_types.schemas._base import TimestampedRead


class BricksPageRead(TimestampedRead):
    id: int
    project_id: int
    page_id: int | None
    slug: str = Field(max_length=255)
    title: str = Field(max_length=512)
    lang: str | None = Field(default=None, max_length=8)
    bricks_schema_version: str | None
    seo_meta: dict[str, Any] | None
    wp_post_id: int | None
    wpml_trid: int | None
    status: ScrapeStatus
    last_import_error: str | None
    # bricks_json se sirve aparte — puede pesar mucho en una página compleja
