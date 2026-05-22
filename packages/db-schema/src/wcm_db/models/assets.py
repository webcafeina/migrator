"""Assets descargados (imágenes, fonts, videos)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import AssetStatus


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("project_id", "hash", name="uq_assets_project_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # sha256 hex
    mime: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    local_path: Mapped[str | None] = mapped_column(String(1024))
    optimized_path: Mapped[str | None] = mapped_column(String(1024))
    r2_key: Mapped[str | None] = mapped_column(String(1024))
    wp_attachment_id: Mapped[int | None] = mapped_column(Integer)
    #: v0.24.0 — Sprint A. NULL = pending upload a WP media library.
    #: Tras `AssetUploaderAgent` exitoso, fija timestamp y permite
    #: idempotencia en re-runs.
    wp_media_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: v0.24.0 — URL canónica del attachment en el destino. Cache para
    #: reescritura masiva de `bricks_pages.bricks_json` sin GET REST
    #: por asset.
    wp_source_url: Mapped[str | None] = mapped_column(String(2048))

    alt_text: Mapped[str | None] = mapped_column(Text)
    sizes_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # thumbnail/medium/large variants

    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status", native_enum=False, length=16),
        nullable=False,
        default=AssetStatus.PENDING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    #: v0.27.0 — score 0.00-1.00 calculado por heurística image_quality.
    #: <0.50 = candidato a regenerar con gpt-image-2. NULL = no analizado
    #: todavía (assets pre-v0.27.0).
    quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=3, scale=2)
    )
    #: v0.27.0 — lista de flags accionables para tooltip en /preview:
    #: ["low_resolution", "obsolete_format", "weird_aspect_ratio", ...]
    quality_flags_json: Mapped[list[str] | None] = mapped_column(JSONB)
