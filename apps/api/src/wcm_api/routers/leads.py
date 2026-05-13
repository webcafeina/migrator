"""Endpoints de leads (lectura + actualización manual + reasignación).

El descubrimiento masivo lo hace el worker (`enqueue_prospect_campaign`).
Aquí solo exponemos lectura y operaciones puntuales (corregir manualmente,
disparar re-fingerprint, etc.).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.leads import Lead
from wcm_types.enums import BuilderType, LeadStatus, UserRole
from wcm_types.schemas.leads import LeadRead, LeadUpdate

from wcm_api.db import get_session
from wcm_api.errors import NotFoundError
from wcm_api.security import require_role
from wcm_api.tasks.enqueue import enqueue_lead_fingerprint

router = APIRouter(prefix="/leads", tags=["leads"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


@router.get("", response_model=list[LeadRead])
async def list_leads(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    sector: str | None = Query(default=None),
    region: str | None = Query(default=None),
    builder: BuilderType | None = Query(default=None),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[LeadRead]:
    stmt = select(Lead)
    if sector:
        stmt = stmt.where(Lead.sector == sector)
    if region:
        stmt = stmt.where(Lead.region == region)
    if builder:
        stmt = stmt.where(Lead.builder_detected == builder)
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if min_score > 0:
        stmt = stmt.where(Lead.score >= min_score)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    leads = (await session.execute(stmt)).scalars().all()
    return [LeadRead.model_validate(l) for l in leads]


@router.get("/count")
async def count_leads(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> dict:
    total = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
    return {"total": int(total)}


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> LeadRead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    return LeadRead.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> LeadRead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(lead, k, v)
    await session.commit()
    await session.refresh(lead)
    return LeadRead.model_validate(lead)


@router.post("/{lead_id}/refingerprint", status_code=status.HTTP_202_ACCEPTED)
async def refingerprint_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    task_id = enqueue_lead_fingerprint(lead_id)
    return {"task_id": task_id, "status": "queued"}
