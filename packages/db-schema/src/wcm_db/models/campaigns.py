"""Campañas de prospección.

Una Campaign es una invocación concreta del flujo
prospect → fingerprint → enrich. Persiste el `task_id` de Celery, los
parámetros del lanzamiento, el estado agregado, los IDs de leads
creados y los timestamps de inicio/fin.

Antes de esta tabla las campañas no se persistían (solo vivían como job
Celery con resultado consultable durante 24h). Se añade en sesión
2026-05-14 para poder mostrar un indicador global multiventana de
campañas en curso (ver feedback usuario en sesión).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin
from wcm_db.enums import CampaignStatus


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: ID del task Celery (`wcm.prospector.run_campaign`). UNIQUE: una
    #: campaña ↔ un task. Útil para el endpoint /campaigns/runs/{task_id}.
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    sector: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", native_enum=False, length=32),
        nullable=False,
        default=CampaignStatus.QUEUED,
        index=True,
    )

    #: User que lanzó la campaña. NULL si vino vía CLI sin auth (raro).
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: IDs de los leads creados por el ProspectorAgent. Se rellena cuando
    #: la task termina; antes está vacío. Permite saber qué leads
    #: pertenecen a esta campaña sin recorrer la tabla `leads`.
    created_lead_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list
    )

    error: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
