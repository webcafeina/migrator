"""Endpoints de secuencias de outreach (lectura + aprobación).

Los borradores los genera el worker (`OutreachComposerAgent`). Aquí el
operador del dashboard:
- Lista secuencias filtradas por status/lead.
- Lee el detalle (incluye los `OutreachSend` renderizados, para preview).
- Aprueba (`DRAFT_PENDING_REVIEW` → `READY`), pausa o cancela.

Los envíos reales (transición READY → IN_PROGRESS → SENT) se realizan en
Fase 10 con Resend. En MVP, "READY" significa que el operador ha dado
el visto bueno; el envío puede ser manual fuera del sistema.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.rate_limit import limiter
from wcm_api.security import TokenPayload, get_current_user_payload, require_role
from wcm_api.tasks.enqueue import enqueue_outreach_send
from wcm_db.models.audit import AuditLog
from wcm_db.models.outreach import OutreachSend, OutreachSequence
from wcm_types.enums import (
    AuditAction,
    OutreachSendStatus,
    OutreachSequenceStatus,
    UserRole,
)
from wcm_types.schemas.outreach import OutreachSendRead, OutreachSequenceRead

router = APIRouter(prefix="/outreach", tags=["outreach"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


class OutreachSequenceDetail(OutreachSequenceRead):
    sends: list[OutreachSendRead]


@router.get("/sequences", response_model=list[OutreachSequenceRead])
async def list_sequences(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    lead_id: int | None = Query(default=None),
    status_filter: OutreachSequenceStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[OutreachSequenceRead]:
    stmt = select(OutreachSequence)
    if lead_id is not None:
        stmt = stmt.where(OutreachSequence.lead_id == lead_id)
    if status_filter is not None:
        stmt = stmt.where(OutreachSequence.status == status_filter)
    stmt = stmt.order_by(OutreachSequence.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [OutreachSequenceRead.model_validate(r) for r in rows]


@router.get("/sequences/{sequence_id}", response_model=OutreachSequenceDetail)
async def get_sequence(
    sequence_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> OutreachSequenceDetail:
    stmt = (
        select(OutreachSequence)
        .where(OutreachSequence.id == sequence_id)
        .options(selectinload(OutreachSequence.sends))
    )
    seq = (await session.execute(stmt)).scalar_one_or_none()
    if seq is None:
        raise NotFoundError(f"Outreach sequence {sequence_id} no encontrada")
    base = OutreachSequenceRead.model_validate(seq)
    sends = [OutreachSendRead.model_validate(s) for s in seq.sends]
    return OutreachSequenceDetail(**base.model_dump(), sends=sends)


class SequenceTransition(BaseModel):
    action: Literal["approve", "pause", "cancel"]


_VALID_TRANSITIONS: dict[str, dict[OutreachSequenceStatus, OutreachSequenceStatus]] = {
    "approve": {
        OutreachSequenceStatus.DRAFT_PENDING_REVIEW: OutreachSequenceStatus.READY,
        OutreachSequenceStatus.PAUSED: OutreachSequenceStatus.READY,
    },
    "pause": {
        OutreachSequenceStatus.READY: OutreachSequenceStatus.PAUSED,
        OutreachSequenceStatus.IN_PROGRESS: OutreachSequenceStatus.PAUSED,
    },
    "cancel": {
        OutreachSequenceStatus.DRAFT_PENDING_REVIEW: OutreachSequenceStatus.COMPLETED,
        OutreachSequenceStatus.READY: OutreachSequenceStatus.COMPLETED,
        OutreachSequenceStatus.PAUSED: OutreachSequenceStatus.COMPLETED,
    },
}


@router.post("/sequences/{sequence_id}/transition", response_model=OutreachSequenceRead)
async def transition_sequence(
    sequence_id: int,
    payload: SequenceTransition,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> OutreachSequenceRead:
    """Aprueba / pausa / cancela una secuencia. Transiciones validadas:

    | from                  | approve | pause   | cancel    |
    |---                    |---      |---      |---        |
    | DRAFT_PENDING_REVIEW  | READY   | -       | COMPLETED |
    | READY                 | -       | PAUSED  | COMPLETED |
    | IN_PROGRESS           | -       | PAUSED  | -         |
    | PAUSED                | READY   | -       | COMPLETED |

    Una vez aprobada (READY), el envío real lo lanza Fase 10. En MVP basta
    con la transición + auditoría.
    """
    seq = await session.get(OutreachSequence, sequence_id)
    if seq is None:
        raise NotFoundError(f"Outreach sequence {sequence_id} no encontrada")
    transitions = _VALID_TRANSITIONS[payload.action]
    new_status = transitions.get(seq.status)
    if new_status is None:
        raise ConflictError(
            f"Transición {payload.action!r} no válida desde estado {seq.status.value}"
        )

    if payload.action == "approve" and not seq.legal_validation_passed:
        raise ConflictError(
            "No se puede aprobar una secuencia que no pasó la validación legal"
        )

    seq.status = new_status
    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.UPDATE,
            entity_type="outreach_sequence",
            entity_id=str(seq.id),
            legal_ground="6.1.f",
            payload={
                "transition": payload.action,
                "new_status": new_status.value,
                "operator_role": user.role,
            },
        )
    )
    await session.commit()
    await session.refresh(seq)
    return OutreachSequenceRead.model_validate(seq)


@router.post("/sequences/{sequence_id}/send", status_code=202)
@limiter.limit("30/minute")
async def send_sequence_step(
    request: Request,
    sequence_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
    step_index: int | None = Query(default=None, ge=0),
) -> dict:
    """Encola el envío del siguiente OutreachSend QUEUED de la secuencia.

    Si `step_index` no se proporciona, dispara el QUEUED de menor index.
    Requiere que la secuencia esté en READY o IN_PROGRESS.
    """
    seq = await session.get(OutreachSequence, sequence_id)
    if seq is None:
        raise NotFoundError(f"Outreach sequence {sequence_id} no encontrada")
    if seq.status not in (
        OutreachSequenceStatus.READY,
        OutreachSequenceStatus.IN_PROGRESS,
    ):
        raise ConflictError(
            f"Sequence {sequence_id} en {seq.status.value}, debe estar READY o IN_PROGRESS"
        )

    stmt = select(OutreachSend).where(
        OutreachSend.sequence_id == sequence_id,
        OutreachSend.status == OutreachSendStatus.QUEUED,
    )
    if step_index is not None:
        stmt = stmt.where(OutreachSend.step_index == step_index)
    stmt = stmt.order_by(OutreachSend.step_index.asc())

    send = (await session.execute(stmt)).scalars().first()
    if send is None:
        raise ConflictError(
            f"Sequence {sequence_id} no tiene ningún OutreachSend en estado QUEUED"
        )

    task_id = enqueue_outreach_send(send.id)

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.SEND,
            entity_type="outreach_send",
            entity_id=str(send.id),
            legal_ground="6.1.f",
            payload={
                "queued_task_id": task_id,
                "sequence_id": sequence_id,
                "step_index": send.step_index,
            },
        )
    )
    await session.commit()
    return {
        "task_id": task_id,
        "status": "queued",
        "send_id": send.id,
        "step_index": send.step_index,
    }
