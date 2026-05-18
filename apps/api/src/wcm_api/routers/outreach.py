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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from wcm_db.models.outreach import EmailLayout, OutreachSend, OutreachSequence
from wcm_types.enums import (
    AuditAction,
    OutreachSendStatus,
    OutreachSequenceStatus,
    UserRole,
)
from wcm_types.schemas.outreach import (
    OutreachPreviewResponse,
    OutreachSendRead,
    OutreachSequenceRead,
    OutreachStepsUpdatePayload,
    OutreachTestSendPayload,
    OutreachTestSendResponse,
)

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
        raise ConflictError("No se puede aprobar una secuencia que no pasó la validación legal")

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


@router.patch("/sequences/{sequence_id}/steps", response_model=OutreachSequenceRead)
async def edit_sequence_steps(
    sequence_id: int,
    payload: OutreachStepsUpdatePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> OutreachSequenceRead:
    """Edita los `steps_json` de una sequence en estado editable
    (`DRAFT_PENDING_REVIEW` o `PAUSED`). Reemplaza la lista completa
    de pasos (semántica de PUT, no merge parcial — el cliente envía
    siempre todos los pasos).

    Tras escribir, re-corre la validación legal sobre los pasos nuevos
    (reusando el mismo helper del composer). Si el resultado NO pasa,
    `legal_validation_passed` queda en False y el endpoint
    `/transition action=approve` quedará bloqueado hasta corregir.
    Devuelve la sequence actualizada para que el cliente refresque la
    UI sin un fetch extra.
    """
    seq = await session.get(OutreachSequence, sequence_id)
    if seq is None:
        raise NotFoundError(f"Outreach sequence {sequence_id} no encontrada")

    # Estados editables: solo borradores o pausados. Una sequence
    # READY/SENT/COMPLETED no se edita — si el operador quiere
    # cambiarla, debe cancelarla y re-componer.
    editable_statuses = {
        OutreachSequenceStatus.DRAFT_PENDING_REVIEW,
        OutreachSequenceStatus.PAUSED,
    }
    if seq.status not in editable_statuses:
        raise ConflictError(
            f"No se pueden editar pasos en estado {seq.status.value!r}. "
            "Cancela y re-compón el draft."
        )

    # Lazy import del worker (mismo patrón que health.py:127).
    from wcm_worker.agents.outreach_composer import (
        load_company_legal_settings,
        validate_outreach_steps,
    )

    new_steps = [s.model_dump() for s in payload.steps]
    company_settings = load_company_legal_settings()
    legal_errors = validate_outreach_steps(new_steps, company_settings)

    seq.steps_json = new_steps
    seq.legal_validation_passed = len(legal_errors) == 0

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.UPDATE,
            entity_type="outreach_sequence",
            entity_id=str(seq.id),
            legal_ground="6.1.f",
            payload={
                "action": "edit_steps",
                "steps_count": len(new_steps),
                "legal_validation_passed": seq.legal_validation_passed,
                "legal_errors": legal_errors[:10],  # cap para no llenar audit log
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
        raise ConflictError(f"Sequence {sequence_id} no tiene ningún OutreachSend en estado QUEUED")

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


# --- v0.14.0: preview HTML del step + test-send ---


async def _load_send_or_404(
    session: AsyncSession, sequence_id: int, step_index: int
) -> OutreachSend:
    stmt = select(OutreachSend).where(
        OutreachSend.sequence_id == sequence_id,
        OutreachSend.step_index == step_index,
    )
    send = (await session.execute(stmt)).scalar_one_or_none()
    if send is None:
        raise NotFoundError(
            f"OutreachSend step={step_index} de sequence {sequence_id} no encontrado"
        )
    return send


async def _render_send_html(send: OutreachSend, session: AsyncSession) -> str:
    """Devuelve el HTML para previsualizar el step. Si el send tiene
    `body_html_rendered` (sends post-v0.14.0) lo retorna directo;
    si NULL (sends legacy) lo regenera on-the-fly envolviendo el
    `body_rendered` texto en HTML básico + layout + premailer.
    """
    if send.body_html_rendered:
        return send.body_html_rendered

    from wcm_worker.integrations.email_layout import (
        EmailLayoutSnapshot,
        load_layout,
        render_full_email,
    )
    from wcm_worker.integrations.html_email import wrap_plain_as_html

    layout_row = await session.get(EmailLayout, 1)
    layout = (
        EmailLayoutSnapshot(layout_html=layout_row.layout_html, layout_css=layout_row.layout_css)
        if layout_row
        else load_layout(None)
    )
    body_html_content = wrap_plain_as_html(send.body_rendered or "")
    # Contexto mínimo legal/branding desde env — el send histórico ya
    # tenía estos valores literales en body_rendered (footer + opt-out).
    # Lo que reconstruimos aquí es el wrapper visual (header/CTA/CSS).
    import os

    ctx = {
        "company_legal_name": os.environ.get("COMPANY_LEGAL_NAME", "Webcafeína S.L."),
        "company_cif": os.environ.get("COMPANY_CIF", ""),
        "company_address": os.environ.get("COMPANY_ADDRESS", ""),
        "company_contact_email": os.environ.get("COMPANY_CONTACT_EMAIL", "info@webcafeina.com"),
        "privacy_policy_url": os.environ.get(
            "COMPANY_PRIVACY_POLICY_URL",
            "https://webcafeina.com/politica-de-privacidad",
        ),
        "opt_out_url": "https://migrator.webcafeina.com/opt-out?token=LEGACY",
        "logo_url": os.environ.get("EMAIL_LOGO_URL", "") or "",
    }
    return render_full_email(
        layout,
        content_html=body_html_content,
        subject=send.subject,
        cta_label=None,
        cta_url=None,
        logo_url=ctx["logo_url"],
        template_ctx=ctx,
    )


@router.get(
    "/sequences/{sequence_id}/steps/{step_index}/preview",
    response_model=OutreachPreviewResponse,
)
async def preview_sequence_step(
    sequence_id: int,
    step_index: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> OutreachPreviewResponse:
    """HTML renderizado del step (snapshot histórico o regenerado).

    El cliente lo pinta en un iframe `srcDoc` para que el operador
    vea exactamente cómo quedará el correo. No requiere RBAC especial
    (cualquier usuario con acceso al lead puede previsualizar).
    """
    send = await _load_send_or_404(session, sequence_id, step_index)
    html = await _render_send_html(send, session)
    return OutreachPreviewResponse(html=html, subject=send.subject)


@router.post(
    "/sequences/{sequence_id}/steps/{step_index}/test-send",
    response_model=OutreachTestSendResponse,
)
@limiter.limit("10/minute")
async def test_send_sequence_step(
    request: Request,
    sequence_id: int,
    step_index: int,
    payload: OutreachTestSendPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> OutreachTestSendResponse:
    """Envía el step a una dirección arbitraria para verificar
    visualmente cómo llega. NO crea OutreachSend ni muta status del
    sequence — solo llama a Resend directo y registra AuditLog
    `TEST_SEND` con `to` para trazabilidad.

    Rate-limited a 10/min por IP para evitar abuso (un operador no
    necesita más; abuso = bug en cliente o intent malicioso).
    """
    send = await _load_send_or_404(session, sequence_id, step_index)
    html = await _render_send_html(send, session)
    text_body = send.body_rendered or ""
    subject = send.subject or ""

    # Lazy import del worker (mismo patrón que el resto del router).
    from wcm_worker.integrations.resend import ResendApiError, ResendClient

    client = ResendClient.from_env()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RESEND_API_KEY no configurada; el envío de prueba no está disponible.",
        )

    try:
        result = client.send(
            to=[payload.to],
            subject=f"[PRUEBA] {subject}" if subject else "[PRUEBA] Test",
            body_text=text_body,
            body_html=html or None,
            tags=[
                {"name": "kind", "value": "test_send"},
                {"name": "sequence_id", "value": str(sequence_id)},
                {"name": "step_index", "value": str(step_index)},
            ],
        )
    except ResendApiError as e:
        # No persistimos error en la BD: el test-send es efímero. El
        # operador ve el toast con el mensaje.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resend rechazó: {e}",
        ) from e

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.TEST_SEND,
            entity_type="outreach_send",
            entity_id=str(send.id),
            legal_ground=None,
            payload={
                "to": payload.to,
                "sequence_id": sequence_id,
                "step_index": step_index,
                "provider_message_id": result.message_id,
                "operator_role": user.role,
            },
        )
    )
    await session.commit()

    return OutreachTestSendResponse(provider_message_id=result.message_id, to=payload.to)
