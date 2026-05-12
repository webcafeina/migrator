"""Tareas residuales — lo que no se automatiza y queda para humanos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import ResidualCategory, ResidualStatus


class ResidualTask(Base, TimestampMixin):
    __tablename__ = "residual_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ResidualCategory] = mapped_column(
        Enum(ResidualCategory, name="residual_category", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    screenshot_paths: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    generated_by: Mapped[str | None] = mapped_column(String(64))  # subagente que la generó

    clickup_task_id: Mapped[str | None] = mapped_column(String(40), index=True)
    assignee_hint: Mapped[str | None] = mapped_column(String(64))  # Álvaro, Samuel, ...

    status: Mapped[ResidualStatus] = mapped_column(
        Enum(ResidualStatus, name="residual_status", native_enum=False, length=16),
        nullable=False,
        default=ResidualStatus.OPEN,
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
