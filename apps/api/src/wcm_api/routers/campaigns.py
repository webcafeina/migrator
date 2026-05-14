"""Campañas de prospección: lanzamiento + estado.

Una campaña representa un conjunto de criterios (sector + región + target)
con métricas asociadas. En MVP no la persistimos como tabla separada —
se modela como job Celery con resultado consultable. Si se vuelve
recurrente, en Fase 9 se puede añadir tabla `campaigns`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from wcm_api.security import require_role
from wcm_api.tasks.enqueue import enqueue_prospect_campaign
from wcm_types.enums import UserRole

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


class LaunchCampaignPayload(BaseModel):
    sector: str = Field(min_length=2, max_length=120)
    region: str = Field(min_length=2, max_length=120)
    target_count: int = Field(default=50, ge=1, le=500)
    exclude_domains: list[str] = Field(default_factory=list, max_length=1000)


@router.post("/launch", status_code=status.HTTP_202_ACCEPTED)
async def launch_campaign(
    payload: LaunchCampaignPayload,
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """Encola la campaña. El worker la ejecutará e irá poblando `leads`."""
    task_id = enqueue_prospect_campaign(
        sector=payload.sector,
        region=payload.region,
        target_count=payload.target_count,
        exclude_domains=payload.exclude_domains,
    )
    return {
        "task_id": task_id,
        "status": "queued",
        "sector": payload.sector,
        "region": payload.region,
        "target_count": payload.target_count,
    }
