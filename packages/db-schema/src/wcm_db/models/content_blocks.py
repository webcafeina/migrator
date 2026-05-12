"""Bloques de contenido semánticos extraídos del HTML scrapeado.

Estructura intermedia entre `scraped_pages` y `bricks_pages`. Lo que
produce content-extractor y consume bricks-transpiler.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import BlockType, ContentBlockSource


class ContentBlock(Base, TimestampMixin):
    __tablename__ = "content_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[int] = mapped_column(
        ForeignKey("scraped_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    block_type: Mapped[BlockType] = mapped_column(
        Enum(BlockType, name="block_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lang: Mapped[str | None] = mapped_column(String(8), index=True)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[ContentBlockSource] = mapped_column(
        Enum(
            ContentBlockSource,
            name="content_block_source",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=ContentBlockSource.EXTRACTED,
    )

    page: Mapped["ScrapedPage"] = relationship(back_populates="content_blocks")  # noqa: F821
