"""Leads de prospección, su enriquecimiento y el log de opt-out RGPD."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import BuilderType, LeadStatus

# Voyage AI multilingual-2 produce 1024 dimensiones — buena cobertura para
# español de PYMEs. Cambiar este valor implica migración compleja del índice
# y re-embedding completo (ver ADR-010).
LEAD_EMBEDDING_DIM = 1024


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("url", name="uq_leads_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    business_name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(120), index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")
    region: Mapped[str | None] = mapped_column(String(120), index=True)

    builder_detected: Mapped[BuilderType | None] = mapped_column(
        Enum(BuilderType, name="builder_type", native_enum=False, length=32),
        index=True,
    )
    builder_confidence: Mapped[float | None] = mapped_column(Float)
    builder_evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    emails: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    phones: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    social_links: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", native_enum=False, length=32),
        nullable=False,
        default=LeadStatus.DISCOVERED,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    last_crawl_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Embedding semántico para búsqueda de leads similares (pgvector). Ver ADR-010.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(LEAD_EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    enrichments: Mapped[list["LeadEnrichment"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    outreach_sequences: Mapped[list["OutreachSequence"]] = relationship(  # noqa: F821
        back_populates="lead", cascade="all, delete-orphan"
    )


class LeadEnrichment(Base, TimestampMixin):
    __tablename__ = "lead_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)  # google_maps, paginas_amarillas, ...
    employees_estimate: Mapped[int | None] = mapped_column(Integer)
    revenue_estimate_eur: Mapped[int | None] = mapped_column(Integer)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    traffic_estimate_monthly: Mapped[int | None] = mapped_column(Integer)
    ahrefs_dr: Mapped[float | None] = mapped_column(Float)

    legal_ground: Mapped[str | None] = mapped_column(String(40))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    lead: Mapped[Lead] = relationship(back_populates="enrichments")


class OptOutLog(Base):
    """Registro permanente de opt-outs. NO se borra, es la base jurídica
    para no recontactar (LSSI-CE).
    """

    __tablename__ = "opt_out_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lead_id_at_optout: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="email")
    evidence: Mapped[str | None] = mapped_column(Text)  # token, mensaje, captura, etc.
    opted_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("email", "channel", name="uq_opt_out_log_email_channel"),
    )
