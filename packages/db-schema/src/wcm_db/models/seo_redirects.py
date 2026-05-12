"""Mapa de redirecciones 301 origen → destino."""

from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin


class SeoRedirect(Base, TimestampMixin):
    __tablename__ = "seo_redirects"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_path", name="uq_seo_redirects_project_source"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    target_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False, default=301)
    wp_redirect_id: Mapped[int | None] = mapped_column(Integer)
