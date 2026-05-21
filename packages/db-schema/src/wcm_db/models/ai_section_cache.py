"""Cache de respuestas Claude Vision para secciones (AI.3 — sprint v0.22.0).

Cada entrada cachea una llamada a Claude Vision con su respuesta
(JSON Bricks elements) indexada por `input_hash = sha256(screenshot
bytes + html + selector)`. El hash es estable entre runs y entre
proyectos del mismo origen, así migrar mariya.design dos veces no
duplica coste API.

`project_id` es nullable + ondelete=SET NULL para que el cache
sobreviva al borrado del proyecto que lo generó.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base


class AiSectionCache(Base):
    __tablename__ = "ai_section_cache"
    __table_args__ = (
        UniqueConstraint("input_hash", name="uq_ai_section_cache_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: sha256 de (screenshot_bytes + html + selector). Estable entre runs.
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Proyecto que generó la entry inicialmente. Nullable para que el
    #: cache sobreviva al borrado del proyecto.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: JSON Bricks elements devuelto por Claude. Forma:
    #: `{"elements": [{id, name, parent, children, settings}, ...]}`.
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    #: Identificador del modelo Claude usado (p.ej. "claude-sonnet-4-6").
    #: Si rotamos modelo, las entries antiguas siguen siendo válidas pero
    #: el operador puede invalidarlas filtrando por este campo.
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
