"""audit_log y error_log — trazabilidad completa de operaciones y errores."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base
from wcm_db.enums import AuditAction, ErrorSeverity


class AuditLog(Base):
    """Registro append-only de operaciones del sistema.

    Sin TimestampMixin: el created_at se gestiona como una columna fija
    `at` con timezone, y nunca se actualiza.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str | None] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    legal_ground: Mapped[str | None] = mapped_column(String(40))


class ErrorLog(Base):
    """Errores capturados del sistema. Conservados ~90 días."""

    __tablename__ = "error_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(Integer, index=True)
    severity: Mapped[ErrorSeverity] = mapped_column(
        Enum(ErrorSeverity, name="error_severity", native_enum=False, length=16),
        nullable=False,
        index=True,
    )
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack: Mapped[str | None] = mapped_column(Text)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sentry_event_id: Mapped[str | None] = mapped_column(String(40))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
