"""Campañas de prospección: lanzamiento + estado + listado en curso.

Cada lanzamiento crea una fila en `campaigns` con el `task_id` Celery,
los parámetros, el estado agregado y los timestamps. La tabla `leads`
referencia a `campaigns.id` vía `lead.campaign_id` para que el enricher
pueda cerrar la campaña cuando todos los leads han pasado por enrich.

Endpoints:
- `POST /launch`: crea Campaign(status=queued), encola task con
  campaign_id, devuelve task_id.
- `GET /runs/{task_id}`: progreso vivo (combinando estado Celery +
  estado actual de los leads).
- `GET /active`: lista de campañas no terminadas para el indicador
  global del dashboard.
"""

from __future__ import annotations

from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.security import TokenPayload, get_current_user_payload, require_role
from wcm_api.tasks.celery_app import celery_app
from wcm_api.tasks.enqueue import enqueue_prospect_campaign
from wcm_db.models.campaigns import Campaign
from wcm_db.models.leads import Lead
from wcm_types.enums import CampaignStatus, UserRole

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


class LaunchCampaignPayload(BaseModel):
    sector: str = Field(min_length=2, max_length=120)
    region: str = Field(min_length=2, max_length=120)
    target_count: int = Field(default=50, ge=1, le=500)
    exclude_domains: list[str] = Field(default_factory=list, max_length=1000)


@router.post("/launch", status_code=status.HTTP_202_ACCEPTED)
async def launch_campaign(
    payload: LaunchCampaignPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(_operator_or_admin)],
) -> dict:
    """Encola la campaña + persiste Campaign(status=queued).

    El worker (`tasks/prospector.run_campaign`) recibe `campaign_id`
    y actualiza el row con `status=running` al empezar y `completed`
    al terminar el enrichment.
    """
    import uuid

    # Encolar primero para obtener task_id real, luego persistir Campaign
    # con ese task_id. El worker hará lookup `SELECT FROM campaigns WHERE
    # task_id = self.request.id` para encontrarse a sí mismo.
    task_id = enqueue_prospect_campaign(
        sector=payload.sector,
        region=payload.region,
        target_count=payload.target_count,
        exclude_domains=payload.exclude_domains,
    )
    user_uuid = uuid.UUID(user.sub) if user.sub else None
    campaign = Campaign(
        task_id=task_id,
        sector=payload.sector,
        region=payload.region,
        target_count=payload.target_count,
        status=CampaignStatus.QUEUED,
        created_by_user_id=user_uuid,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)

    return {
        "task_id": task_id,
        "campaign_id": campaign.id,
        "status": "queued",
        "sector": payload.sector,
        "region": payload.region,
        "target_count": payload.target_count,
    }


# ---------- ACTIVE ----------

@router.get("/active")
async def list_active_campaigns(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> list[dict]:
    """Devuelve campañas no terminadas (queued|running) ordenadas por más
    reciente primero. Sirve al indicador global del header del dashboard.
    """
    stmt = (
        select(Campaign)
        .where(Campaign.status.in_([CampaignStatus.QUEUED, CampaignStatus.RUNNING]))
        .order_by(desc(Campaign.started_at))
        .limit(20)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": c.id,
            "task_id": c.task_id,
            "sector": c.sector,
            "region": c.region,
            "target_count": c.target_count,
            "status": c.status.value,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "lead_count": len(c.created_lead_ids or []),
        }
        for c in rows
    ]


@router.get("/runs/{task_id}")
async def campaign_run_status(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> dict:
    """Estado vivo de una campaña: prospect (counters) + pipeline (status leads).

    El frontend polea cada 2s y para cuando `ready` y `pipeline.enriched
    == pipeline.total`. Si la task expiró del backend Celery, `state`
    será PENDING — no podemos distinguirlo de "aún no empezada".
    """
    async_result = AsyncResult(task_id, app=celery_app)
    state = async_result.state  # PENDING|STARTED|SUCCESS|FAILURE|RETRY
    response: dict = {
        "task_id": task_id,
        "state": state,
        "ready": async_result.ready(),
        "prospect": None,
        "pipeline": None,
        "error": None,
    }

    if state == "FAILURE":
        response["error"] = str(async_result.result) if async_result.result else "unknown"
        return response

    if state != "SUCCESS":
        return response

    # SUCCESS: leer outputs serializados por la task
    payload = async_result.result or {}
    if payload.get("status") == "error":
        response["error"] = payload.get("error", "unknown")
        return response

    outputs = payload.get("outputs", {}) or {}
    response["prospect"] = {
        "query": outputs.get("query"),
        "discovered": outputs.get("discovered", 0),
        "created": outputs.get("created", 0),
        "skipped_duplicate": outputs.get("skipped_duplicate", 0),
        "skipped_no_website": outputs.get("skipped_no_website", 0),
        "skipped_excluded": outputs.get("skipped_excluded", 0),
        "skipped_blocked_type": outputs.get("skipped_blocked_type", 0),
        "warnings": payload.get("warnings", []),
    }

    lead_ids: list[int] = outputs.get("created_lead_ids", []) or []
    if not lead_ids:
        response["pipeline"] = {"total": 0, "by_status": {}, "lead_ids": []}
        return response

    # Estado actual de los leads (puede haber cambiado desde que terminó
    # el prospector — fingerprint/enrich corren después en chain).
    stmt = (
        select(Lead.status, func.count())
        .where(Lead.id.in_(lead_ids))
        .group_by(Lead.status)
    )
    rows = (await session.execute(stmt)).all()
    by_status: dict[str, int] = {}
    for status_enum, count in rows:
        key = status_enum.value if hasattr(status_enum, "value") else str(status_enum)
        by_status[key] = count

    response["pipeline"] = {
        "total": len(lead_ids),
        "by_status": by_status,
        "lead_ids": lead_ids,
    }
    return response
