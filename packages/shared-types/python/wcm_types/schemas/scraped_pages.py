from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from wcm_types.enums import ScrapeStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class ScrapedPageRead(TimestampedRead):
    id: int
    project_id: int
    url: HttpUrl
    slug: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=512)
    lang: str | None = Field(default=None, max_length=8)
    depth: int
    screenshot_path: str | None
    screenshot_mobile_path: str | None
    status: ScrapeStatus
    scraped_at: datetime | None
    error_message: str | None
    # NO incluimos html_raw/html_clean/dom_tree_json/css_extracted en serialización
    # default — son demasiado pesados. La API expone endpoint específico para ellos.
