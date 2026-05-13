"""Webhooks entrantes.

- ClickUp: eventos `taskStatusUpdated` actualizan `residual_tasks.status`.
- Resend: eventos `email.delivered`, `email.opened`, `email.bounced`,
  `email.complained` actualizan `OutreachSend` correspondiente.

Sin auth de operador — el secret HMAC es la autenticación.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.audit import AuditLog
from wcm_db.models.outreach import OutreachSend
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import AuditAction, OutreachSendStatus, ResidualStatus

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


# ---------- Resend webhook ----------

def _verify_resend_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Resend firma con HMAC SHA-256 hex sobre el body crudo en `svix-signature`."""
    if not signature:
        return False
    # Resend/Svix incluye uno o varios pares "v1,<hex>" separados por espacio.
    # Para simplicidad aceptamos un hex puro O un par v1,<hex>.
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    for part in signature.split():
        cand = part.split(",", 1)[-1]
        if hmac.compare_digest(expected, cand):
            return True
    return False


_RESEND_EVENT_FIELD: dict[str, str] = {
    "email.sent": "sent_at",
    "email.delivered": "sent_at",
    "email.opened": "opened_at",
    "email.bounced": "bounced_at",
    "email.complained": "bounced_at",
    "email.delivery_delayed": "sent_at",
}


_RESEND_EVENT_STATUS: dict[str, OutreachSendStatus] = {
    "email.sent": OutreachSendStatus.SENT,
    "email.delivered": OutreachSendStatus.SENT,
    "email.opened": OutreachSendStatus.OPENED,
    "email.bounced": OutreachSendStatus.BOUNCED,
    "email.complained": OutreachSendStatus.BOUNCED,
}


@router.post("/resend", status_code=status.HTTP_204_NO_CONTENT)
async def resend_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
    svix_signature: Annotated[str | None, Header()] = None,
) -> None:
    secret = settings.resend_webhook_secret
    if not secret:
        raise UnauthorizedError("RESEND_WEBHOOK_SECRET no configurado")

    body = await request.body()
    if not _verify_resend_signature(body, svix_signature, secret):
        log.warning("resend_webhook_invalid_signature")
        raise UnauthorizedError("Firma HMAC inválida")

    payload = await request.json()
    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    message_id = data.get("email_id") or data.get("id")

    if not message_id:
        log.warning("resend_webhook_no_message_id", extra={"type": event_type})
        return None

    stmt = select(OutreachSend).where(OutreachSend.provider_message_id == str(message_id))
    send = (await session.execute(stmt)).scalar_one_or_none()
    if send is None:
        log.debug("resend_webhook_no_send_match", extra={"message_id": message_id})
        return None

    now = datetime.now(timezone.utc)
    field = _RESEND_EVENT_FIELD.get(event_type)
    if field and getattr(send, field, None) is None:
        setattr(send, field, now)

    new_status = _RESEND_EVENT_STATUS.get(event_type)
    if new_status is not None:
        # Una vez OPENED, no degradamos a SENT. Una vez BOUNCED, terminal.
        send.status = _highest_status(send.status, new_status)

    session.add(
        AuditLog(
            actor="resend-webhook",
            action=AuditAction.UPDATE,
            entity_type="outreach_send",
            entity_id=str(send.id),
            payload={"event": event_type, "message_id": str(message_id)},
        )
    )
    await session.commit()
    return None


_STATUS_PRIORITY: dict[OutreachSendStatus, int] = {
    OutreachSendStatus.QUEUED: 0,
    OutreachSendStatus.SENT: 1,
    OutreachSendStatus.OPENED: 2,
    OutreachSendStatus.REPLIED: 3,
    OutreachSendStatus.BOUNCED: 4,
    OutreachSendStatus.FAILED: 5,
}


def _highest_status(
    current: OutreachSendStatus, candidate: OutreachSendStatus
) -> OutreachSendStatus:
    """Una vez avanzado, no retrocedemos (excepto a estados terminales)."""
    if _STATUS_PRIORITY.get(candidate, 0) >= _STATUS_PRIORITY.get(current, 0):
        return candidate
    return current
