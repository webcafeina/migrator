"""Páginas ya transpiladas a JSON nativo de Bricks Builder."""

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
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import ScrapeStatus


class BricksPage(Base, TimestampMixin):
    __tablename__ = "bricks_pages"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "slug", "lang", name="uq_bricks_pages_project_slug_lang"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("scraped_pages.id", ondelete="SET NULL"), index=True
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    lang: Mapped[str | None] = mapped_column(String(8))

    bricks_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bricks_schema_version: Mapped[str | None] = mapped_column(String(16))
    seo_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    wp_post_id: Mapped[int | None] = mapped_column(Integer, index=True)
    wpml_trid: Mapped[int | None] = mapped_column(Integer, index=True)

    status: Mapped[ScrapeStatus] = mapped_column(
        Enum(ScrapeStatus, name="scrape_status", native_enum=False, length=16),
        nullable=False,
        default=ScrapeStatus.PENDING,
        index=True,
    )
    last_import_error: Mapped[str | None] = mapped_column(Text)

    #: v0.26.0 — URL R2 del thumbnail Playwright sobre el draft WP.
    #: Lo persiste `PreviewThumbnailsAgent` tras `wp_deployer`.
    preview_thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    #: v0.26.0 — timestamp de la última captura. Si `updated_at >
    #: preview_captured_at`, el thumbnail está stale.
    preview_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
