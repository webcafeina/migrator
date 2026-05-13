"""Health y readiness probes.

- `/health`: el proceso responde. Cheap, no toca DB.
- `/ready`: dependencias arriba (DB + Redis). Más caro, usar como readiness
  para load balancer (Nginx upstream check / k8s readiness).

Ambas sin auth — son endpoints internos para Nginx y monitoreo.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def ready(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Comprueba que la BD responde a SELECT 1. Si falla, retorna 503."""
    from fastapi import HTTPException

    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"db": "unavailable", "error": str(e)[:200]},
        )
    return {"status": "ready", "db": "ok"}
