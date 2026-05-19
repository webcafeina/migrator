"""Comparaciones visuales página-a-página de la web destino vs origen.

Pobladas por `VisualDiffAgent` en la fase `visual_diff` del pipeline
de migración. Una fila por página comparada. El `score` es float 0-1:
1.0 = idénticas, 0.0 = totalmente diferentes (umbral por defecto en
v0.16.0: ≥0.85 considerado OK).

Las 3 URLs apuntan a R2: la captura del origen, la del destino y un
overlay con las zonas divergentes resaltadas en rojo. Si R2 no está
configurado, caen a paths `file://...` locales (utilidad limitada).

Decisión: histórico NO — solo guardamos la última comparación por
`(project_id, page_path)` con UPSERT. Si el operador re-ejecuta
visual-diff (e.g. tras un fix), las filas previas se reemplazan.
"""

from __future__ import annotations

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin


class VisualDiff(Base, TimestampMixin):
    __tablename__ = "visual_diffs"
    __table_args__ = (
        UniqueConstraint("project_id", "page_path", name="uq_visual_diffs_project_page"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Path relativo (sin host). Ej: "/", "/contacto", "/blog/post-1".
    page_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    # URLs públicas (R2 si configurado; `file://` o vacío como fallback).
    source_screenshot_url: Mapped[str | None] = mapped_column(String(1024))
    target_screenshot_url: Mapped[str | None] = mapped_column(String(1024))
    overlay_url: Mapped[str | None] = mapped_column(String(1024))
    # Score 0-1 (pixelmatch ratio invertido: 1 - diff_pixels/total).
    score: Mapped[float | None] = mapped_column(Float)
    viewport_width: Mapped[int] = mapped_column(Integer, nullable=False, default=1280)
