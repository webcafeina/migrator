"""Lectura del error_log para el panel /errors del dashboard.

Solo lectura. El log se popula desde structlog → handler de Sentry/Logtail
que también escribe a `error_log` (a configurar en Fase 11 observabilidad).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
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
