"""Proyectos de migración + sus fases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import BuilderType, ProjectPhaseStatus, ProjectStatus


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    target_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    builder_source: Mapped[BuilderType | None] = mapped_column(
        Enum(BuilderType, name="builder_type", native_enum=False, length=32)
    )

    has_ecommerce: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_multilang: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    langs: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    primary_lang: Mapped[str | None] = mapped_column(String(8))

    asset_storage: Mapped[str] = mapped_column(
        String(16), nullable=False, default="wp_local"
    )  # 'r2' | 'wp_local' — ver WCM-004

    preserve_paths: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    hosting_target_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    theme_styles_origin: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    visual_diff_ignore: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    visual_diff_avg_score: Mapped[float | None] = mapped_column(Float)
    deploy_credentials_encrypted: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[str | None] = mapped_column(String(40))  # basic | standard | premium

    # v0.16.0 — URLs R2 del checklist generado por `checklist-generator`.
    # `null` hasta que el agent ejecute. Si R2 no está configurado el
    # agent persiste paths `file://...` locales (utilidad limitada).
    checklist_md_url: Mapped[str | None] = mapped_column(String(500))
    checklist_pdf_url: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, length=32),
        nullable=False,
        default=ProjectStatus.QUEUED,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_go_live_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    phases: Mapped[list[ProjectPhase]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectPhase(Base, TimestampMixin):
    __tablename__ = "project_phases"
    __table_args__ = (
        UniqueConstraint("project_id", "phase_name", name="uq_project_phases_project_phase"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProjectPhaseStatus] = mapped_column(
        Enum(
            ProjectPhaseStatus,
            name="project_phase_status",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=ProjectPhaseStatus.PENDING,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_log: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    project: Mapped[Project] = relationship(back_populates="phases")
