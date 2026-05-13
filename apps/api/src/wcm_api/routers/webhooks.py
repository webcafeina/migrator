"""Webhooks entrantes.

ClickUp envía eventos `taskStatusUpdated`/`taskCommentPosted` cuando algo
cambia en una tarea sincronizada. Validamos firma HMAC SHA-256 antes de
actuar.

Sin auth de operador — el secret HMAC es la autenticación.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import ResidualStatus

from wcm_api.config import ApiSettings, get_settings
from wcm_api.db import get_session
from wcm_api.errors import UnauthorizedError

log = logging.getLogger("wcm.api.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_clickup_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """ClickUp firma con HMAC SHA-256 hex en el header `X-Signature`."""
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/clickup", status_code=status.HTTP_204_NO_CONTENT)
async def clickup_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
    x_signature: Annotated[str | None, Header()] = None,
) -> None:
    secret = settings.clickup_webhook_secret
    if not secret:
        raise UnauthorizedError("CLICKUP_WEBHOOK_SECRET no configurado")

    body = await request.body()
    if not _verify_clickup_signature(body, x_signature, secret):
        log.warning("clickup_webhook_invalid_signature", extra={"ip": request.client.host if request.client else None})
        raise UnauthorizedError("Firma HMAC inválida")

    payload = await request.json()
    event = payload.get("event")
    task_id = payload.get("task_id") or (payload.get("history_items", [{}])[0].get("data", {}).get("task_id"))

    if not event or not task_id:
        log.warning("clickup_webhook_payload_incomplete", extra={"event": event, "task_id": task_id})
        return None

    if event == "taskStatusUpdated":
        # Buscar residual_task por clickup_task_id
        stmt = select(ResidualTask).where(ResidualTask.clickup_task_id == str(task_id))
        residual = (await session.execute(stmt)).scalar_one_or_none()
        if residual is None:
            log.debug("clickup_webhook_no_residual_match", extra={"clickup_task_id": task_id})
            return None
        new_status = payload.get("status", {}).get("status", "").lower()
        if new_status in ("complete", "closed", "done"):
            residual.status = ResidualStatus.DONE
        elif new_status in ("in progress", "in_progress"):
            residual.status = ResidualStatus.IN_PROGRESS
        elif new_status in ("blocked", "on hold"):
            residual.status = ResidualStatus.BLOCKED
        await session.commit()

    return None
