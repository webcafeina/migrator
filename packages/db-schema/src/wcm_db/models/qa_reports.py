"""Reportes de QA automática post-deploy.

Pobladas por `QaRunnerAgent` en la fase `qa` del pipeline. Una fila
por ejecución (la última gana). Conservamos histórico para diagnosticar
regresiones entre re-ejecuciones del operador.

Scores Lighthouse normalizados 0-100 (compatibles con la UI). NULL si
Lighthouse no estaba disponible y la fase se skippeó parcialmente.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wcm_db.base import Base, TimestampMixin


class QaReport(Base, TimestampMixin):
    __tablename__ = "qa_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Lighthouse scorings (0-100). NULL si Lighthouse no disponible.
    lighthouse_perf_desktop: Mapped[int | None] = mapped_column(SmallInteger)
    lighthouse_perf_mobile: Mapped[int | None] = mapped_column(SmallInteger)
    lighthouse_a11y_avg: Mapped[int | None] = mapped_column(SmallInteger)
    lighthouse_best_practices_avg: Mapped[int | None] = mapped_column(SmallInteger)
    lighthouse_seo_avg: Mapped[int | None] = mapped_column(SmallInteger)

    # HTML validator W3C.
    html_validator_errors_count: Mapped[int] = mapped_column(Integer, default=0)
    html_validator_warnings_count: Mapped[int] = mapped_column(Integer, default=0)

    # Link checker.
    broken_links_count: Mapped[int] = mapped_column(Integer, default=0)
    total_links_checked: Mapped[int] = mapped_column(Integer, default=0)

    # Comprobaciones binarias.
    https_valid: Mapped[bool | None] = mapped_column(Boolean)
    robots_accessible: Mapped[bool | None] = mapped_column(Boolean)
    sitemap_accessible: Mapped[bool | None] = mapped_column(Boolean)

    # Reporte completo (Lighthouse JSON + lista errores HTML + broken links
    # detalle) para drill-down desde la UI sin re-ejecutar el agent.
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
