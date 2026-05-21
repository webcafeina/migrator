"""Páginas origen scrapeadas por scraper-origin."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import ScrapeStatus


class ScrapedPage(Base, TimestampMixin):
    __tablename__ = "scraped_pages"
    __table_args__ = (
        UniqueConstraint("project_id", "url", name="uq_scraped_pages_project_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    lang: Mapped[str | None] = mapped_column(String(8), index=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    html_raw: Mapped[str | None] = mapped_column(Text)
    html_clean: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024))
    screenshot_mobile_path: Mapped[str | None] = mapped_column(String(1024))
    dom_tree_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    css_extracted: Mapped[str | None] = mapped_column(Text)
    #: AI.1 — URLs R2 de cada sección top-level recortada por scraper_origin.
    #: Forma: `[{idx: 0, selector: "section[data-mesh-id='...']", url: "..."}]`.
    #: Consumido por content_extractor para denormalizar en content_blocks y
    #: por ai_assist para alimentar Claude Vision.
    section_screenshots_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    status: Mapped[ScrapeStatus] = mapped_column(
        Enum(ScrapeStatus, name="scrape_status", native_enum=False, length=16),
        nullable=False,
        default=ScrapeStatus.PENDING,
        index=True,
    )
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    content_blocks: Mapped[list[ContentBlock]] = relationship(  # noqa: F821
        back_populates="page", cascade="all, delete-orphan"
    )
