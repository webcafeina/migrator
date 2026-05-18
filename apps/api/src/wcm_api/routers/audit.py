"""Lectura del `audit_log` para el feed de actividad del Overview.

Hasta ahora los routers escribían en `audit_log` pero no había forma de
leerlo desde el dashboard. Este router expone una lectura paginada con
filtros básicos (rango temporal, tipo de acción, tipo de entidad).

El feed agrupa por día en cliente; el endpoint devuelve un timeline plano
ordenado por `at` DESC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.security import require_role
from wcm_db.models.audit import AuditLog
from wcm_types.enums import AuditAction, UserRole

router = APIRouter(prefix="/audit-log", tags=["audit-log"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)


class AuditLogEntry(BaseModel):
    """Vista de lectura de una entrada de audit_log."""

    id: UUID
    at: datetime
    actor: str
    action: AuditAction
    entity_type: str | None
    entity_id: str | None
    payload: dict[str, Any] | None
    legal_ground: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditLogEntry])
async def list_audit_log(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    limit: int = Query(default=50, ge=1, le=200),
    since: datetime | None = Query(
        default=None,
        description="ISO datetime. Si se omite, últimos 7 días.",
    ),
    action: AuditAction | None = Query(
        default=None, description="Filtra por tipo de acción."
    ),
    entity_type: str | None = Query(
        default=None,
        description="Filtra por tipo de entidad (lead, project, campaign...).",
    ),
    entity_id: str | None = Query(default=None),
    actor: str | None = Query(default=None),
) -> list[AuditLogEntry]:
    """Lee entradas del audit_log ordenadas por `at` DESC.

    Por defecto devuelve los últimos 7 días — suficiente para el feed
    de actividad del Overview. Si necesitas más histórico, pasa `since`
    con la fecha de corte.
    """
    if since is None:
        since = datetime.now(UTC) - timedelta(days=7)

    stmt = select(AuditLog).where(AuditLog.at >= since)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    stmt = stmt.order_by(AuditLog.at.desc()).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    return [AuditLogEntry.model_validate(r) for r in rows]
