"""Secuencias de outreach + log de envíos."""

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
from wcm_db.enums import OutreachChannel, OutreachSendStatus, OutreachSequenceStatus


class OutreachSequence(Base, TimestampMixin):
    __tablename__ = "outreach_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_name: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel, name="outreach_channel", native_enum=False, length=16),
        nullable=False,
        default=OutreachChannel.EMAIL,
    )
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutreachSequenceStatus] = mapped_column(
        Enum(
            OutreachSequenceStatus,
            name="outreach_sequence_status",
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=OutreachSequenceStatus.DRAFT_PENDING_REVIEW,
        index=True,
    )
    legal_validation_passed: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    legal_validator_version: Mapped[str | None] = mapped_column(String(16))

    lead: Mapped[Lead] = relationship(back_populates="outreach_sequences")  # noqa: F821
    sends: Mapped[list[OutreachSend]] = relationship(
        back_populates="sequence", cascade="all, delete-orphan"
    )


class OutreachSend(Base, TimestampMixin):
    __tablename__ = "outreach_sends"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id", "step_index", name="uq_outreach_sends_sequence_step"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sequence_id: Mapped[int] = mapped_column(
        ForeignKey("outreach_sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel, name="outreach_channel", native_enum=False, length=16),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(255))
    body_rendered: Mapped[str | None] = mapped_column(Text)
    status: Mapped[OutreachSendStatus] = mapped_column(
        Enum(OutreachSendStatus, name="outreach_send_status", native_enum=False, length=16),
        nullable=False,
        default=OutreachSendStatus.QUEUED,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    # Mensaje de error legible cuando status=FAILED (ej. "Resend rechazó:
    # The webcafeina.com domain is not verified"). Permite al operador
    # diagnosticar sin SSHear al servidor a leer logs. Capado a 1000
    # chars — errores típicos de proveedores SMTP/Resend son <500.
    error_message: Mapped[str | None] = mapped_column(String(1000))

    sequence: Mapped[OutreachSequence] = relationship(back_populates="sends")


class OutreachTemplate(Base, TimestampMixin):
    """Plantillas Jinja2 reutilizables que el composer aplica al generar
    drafts. Migradas a BD en v0.12.0 desde ficheros `.j2` para que el
    equipo pueda editarlas desde el dashboard sin tocar código.

    El composer mantiene fallback a los `.j2` históricos si la BD no
    contiene una plantilla con el `name` solicitado — degradación
    grácil en entornos sin migración aplicada o tests.

    `subject_template` y `body_template` son strings Jinja2 puros. La
    validación legal corre al GENERAR el draft (sobre los pasos
    renderizados), no sobre el template per se.
    """

    __tablename__ = "outreach_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # name único — el composer recibe `template_name` como string opaco
    # y resuelve por este campo.
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    # ISO 639-1 lowercase. "es" / "en". Permite tener variantes por
    # idioma del mismo arquetipo.
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")
