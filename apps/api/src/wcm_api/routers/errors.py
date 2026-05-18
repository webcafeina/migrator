"""Lectura del error_log para el panel /errors del dashboard.

Solo lectura. El log se popula desde structlog → handler de Sentry/Logtail
que también escribe a `error_log` (a configurar en Fase 11 observabilidad).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.security import require_role
from wcm_db.models.audit import ErrorLog
from wcm_types.enums import ErrorSeverity, UserRole
from wcm_types.schemas.audit import ErrorLogRead

router = APIRouter(prefix="/errors", tags=["errors"])

_admin_or_operator = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


@router.get("", response_model=list[ErrorLogRead])
async def list_errors(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_or_operator)],
    severity: ErrorSeverity | None = Query(default=None),
    component: str | None = Query(default=None),
    project_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ErrorLogRead]:
    stmt = select(ErrorLog).order_by(desc(ErrorLog.at))
    if severity:
        stmt = stmt.where(ErrorLog.severity == severity)
    if component:
        stmt = stmt.where(ErrorLog.component == component)
    if project_id is not None:
        stmt = stmt.where(ErrorLog.project_id == project_id)
    stmt = stmt.limit(limit).offset(offset)
    items = (await session.execute(stmt)).scalars().all()
    return [ErrorLogRead.model_validate(e) for e in items]


class ErrorStats(BaseModel):
    """Agregados del error_log para el topbar de `/errors`. Counts por
    severidad (5 buckets) + el primer critical pendiente de mirar +
    distinct components afectados en los últimos 7 días.
    """

    total: int = Field(description="Total entradas en la ventana.")
    critical: int
    error: int
    warning: int
    info: int
    debug: int
    distinct_components: int
    last_critical_at: datetime | None = Field(
        description="Fecha del último critical; null si no hay."
    )


@router.get("/stats", response_model=ErrorStats)
async def error_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_or_operator)],
    since_hours: int = Query(
        default=24 * 7,
        ge=1,
        le=24 * 90,
        description="Ventana hacia atrás en horas. Default 7 días.",
    ),
) -> ErrorStats:
    """Agregados de errores en la ventana configurable (default 7 días).

    `last_critical_at` permite al dashboard pintar un dot rojo si hubo
    un crítico reciente — más útil que un simple count.
    """
    since = datetime.now(UTC) - timedelta(hours=since_hours)
    base = select(func.count()).select_from(ErrorLog).where(ErrorLog.at >= since)

    total = (await session.execute(base)).scalar_one()
    critical = (
        await session.execute(
            base.where(ErrorLog.severity == ErrorSeverity.CRITICAL)
        )
    ).scalar_one()
    error = (
        await session.execute(
            base.where(ErrorLog.severity == ErrorSeverity.ERROR)
        )
    ).scalar_one()
    warning = (
        await session.execute(
            base.where(ErrorLog.severity == ErrorSeverity.WARNING)
        )
    ).scalar_one()
    info = (
        await session.execute(
            base.where(ErrorLog.severity == ErrorSeverity.INFO)
        )
    ).scalar_one()
    debug = (
        await session.execute(
            base.where(ErrorLog.severity == ErrorSeverity.DEBUG)
        )
    ).scalar_one()
    distinct_components = (
        await session.execute(
            select(func.count(func.distinct(ErrorLog.component))).where(
                ErrorLog.at >= since
            )
        )
    ).scalar_one()
    last_critical = (
        await session.execute(
            select(ErrorLog.at)
            .where(ErrorLog.severity == ErrorSeverity.CRITICAL)
            .where(ErrorLog.at >= since)
            .order_by(desc(ErrorLog.at))
            .limit(1)
        )
    ).scalar_one_or_none()

    return ErrorStats(
        total=int(total),
        critical=int(critical),
        error=int(error),
        warning=int(warning),
        info=int(info),
        debug=int(debug),
        distinct_components=int(distinct_components),
        last_critical_at=last_critical,
    )
