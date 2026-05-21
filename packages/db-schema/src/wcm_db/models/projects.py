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
    #: v0.23.0 — Lista deduplicada de globalClasses emitidas por el
    #: transpiler (`{id, name, settings}`). El wp_deployer la serializa
    #: al option `bricks_global_classes` del destino.
    bricks_global_classes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    visual_diff_ignore: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    visual_diff_avg_score: Mapped[float | None] = mapped_column(Float)
    deploy_credentials_encrypted: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[str | None] = mapped_column(String(40))  # basic | standard | premium

    # v0.16.0 — URLs R2 del checklist generado por `checklist-generator`.
    # `null` hasta que el agent ejecute. Si R2 no está configurado el
    # agent persiste paths `file://...` locales (utilidad limitada).
    checklist_md_url: Mapped[str | None] = mapped_column(String(500))
    checklist_pdf_url: Mapped[str | None] = mapped_column(String(500))

    # v0.18.0 — acceso al back del origen + onboarding asistido.
    # `source_access_mode`:
    #   - 'none' (default): scraping HTTP público, sin credenciales.
    #   - 'api': el cliente nos dio API key/token oficial (Wix REST v3,
    #     Webflow Sites API) → `scraper-origin` la usa con fallback a
    #     Playwright si falla.
    #   - 'full': acceso completo al back (login admin). Reservado para
    #     futuro; hoy se trata como 'api'.
    source_access_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none", server_default="none"
    )
    # JSON cifrado con Fernet (misma clave que deploy_credentials_encrypted).
    # Estructura depende del builder:
    #   Wix:     {"api_key": "...", "site_id": "..."}
    #   Webflow: {"api_token": "...", "site_id": "..."}
    source_credentials_encrypted: Mapped[str | None] = mapped_column(Text)
    # Cache del último resultado del endpoint POST /preflight.
    preflight_results_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preflight_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # v0.20.0 (ADR-042) — snapshot SQL del WP destino antes del deploy_wp.
    # Path al fichero .sql en el servidor remoto (no en local del worker).
    # NULL = proyecto pre-v0.20.0 o snapshot falló → rollback MVP (DELETE).
    pre_deploy_snapshot_path: Mapped[str | None] = mapped_column(String(500))
    pre_deploy_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # v0.20.0 (ADR-044) — threshold visual_diff configurable por proyecto.
    # NULL = usa env VISUAL_DIFF_RESIDUAL_THRESHOLD (default 0.70).
    # Rango 0-1 validado en BD vía CHECK constraint.
    visual_diff_threshold: Mapped[float | None] = mapped_column(Float)

    # v0.20.0 (ADR-050) — cap max_pages configurable por proyecto.
    # NULL = usa env SCRAPE_MAX_PAGES_DEFAULT (default 50). Rango 1-500.
    max_pages_scrape: Mapped[int | None] = mapped_column(Integer)

    @property
    def has_source_credentials(self) -> bool:
        """Derived field expuesto en ProjectRead — no expone el
        ciphertext, solo si hay algo configurado. Pydantic con
        `from_attributes=True` lo recoge automáticamente."""
        return bool(self.source_credentials_encrypted)

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
