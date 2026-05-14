"""OutreachSenderAgent — envía un OutreachSend específico vía Resend.

Es la otra cara del OutreachComposerAgent (que solo crea drafts). Aquí:

1. Recibe `outreach_send_id` en `ctx.extra`.
2. Carga el OutreachSend.
3. Comprueba precondiciones:
   - Send.status == QUEUED.
   - Sequence.status ∈ {READY, IN_PROGRESS}.
   - El lead NO está en opt_out_log.
4. Llama a Resend para enviar.
5. Persiste `provider_message_id`, `sent_at=now`, `status=SENT`. Si era
   el primer step, cambia la secuencia a IN_PROGRESS.
6. AuditLog action=SEND con legal_ground=6.1.f.

Errores:
- Send no QUEUED → OutreachSenderError("estado inválido") con código.
- Lead opted-out → marca Send como FAILED y NO envía.
- Resend falla → Send status=FAILED, error_message persistido.

Notas legales: nunca enviamos sin que el operador haya transicionado la
secuencia a READY (validado en /transition con el flag
`legal_validation_passed`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from wcm_db.models.audit import AuditLog
from wcm_db.models.leads import Lead, OptOutLog
from wcm_db.models.outreach import OutreachSend, OutreachSequence
from wcm_types.enums import (
    AuditAction,
    OutreachSendStatus,
    OutreachSequenceStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import OutreachSenderError
from wcm_worker.integrations.resend import ResendApiError, ResendClient

log = logging.getLogger("wcm.worker.outreach_sender")


class OutreachSenderAgent(BaseAgent):
    name = "outreach-sender"
    phase_name = "send_outreach"

    def __init__(self, client: ResendClient | None = None) -> None:
        self._injected_client = client

    def run(self, ctx: AgentContext) -> AgentResult:
        send_id = ctx.extra.get("outreach_send_id")
        if send_id is None:
            raise OutreachSenderError("Requiere ctx.extra['outreach_send_id']")

        send = ctx.session.get(OutreachSend, send_id)
        if send is None:
            raise OutreachSenderError(f"OutreachSend {send_id} no encontrado")

        if send.status != OutreachSendStatus.QUEUED:
            raise OutreachSenderError(
                f"OutreachSend {send_id} en estado {send.status.value}, esperado QUEUED"
            )

        seq = ctx.session.get(OutreachSequence, send.sequence_id)
        if seq is None:
            raise OutreachSenderError(f"OutreachSequence {send.sequence_id} no encontrada")
        if seq.status not in (OutreachSequenceStatus.READY, OutreachSequenceStatus.IN_PROGRESS):
            raise OutreachSenderError(
                f"Sequence {seq.id} en estado {seq.status.value}, debe estar READY o IN_PROGRESS"
            )

        lead = ctx.session.get(Lead, send.lead_id)
        if lead is None:
            raise OutreachSenderError(f"Lead {send.lead_id} desaparecido")
        if not lead.emails:
            send.status = OutreachSendStatus.FAILED
            ctx.session.flush()
            raise OutreachSenderError(f"Lead {lead.id} sin email — no se puede enviar")

        # Doble check anti-spam: opt-out log
        opted = self._check_opted_out(ctx, lead.emails)
        if opted:
            send.status = OutreachSendStatus.FAILED
            ctx.session.add(
                AuditLog(
                    actor="outreach-sender",
                    action=AuditAction.OPT_OUT,
                    entity_type="outreach_send",
                    entity_id=str(send.id),
                    legal_ground="6.1.f",
                    payload={"reason": "lead_opted_out_at_send_time", "email": opted},
                )
            )
            ctx.session.flush()
            raise OutreachSenderError(
                f"Lead {lead.id} en opt_out_log ({opted}) — abortado envío"
            )

        client = self._injected_client or ResendClient.from_env()
        if client is None:
            log.warning("outreach_send_skipped_no_resend_key", extra={"send_id": send.id})
            return AgentResult(
                summary=f"Send {send.id} skipped (no RESEND_API_KEY)",
                outputs={"skipped": True},
            )

        try:
            result = client.send(
                to=[lead.emails[0]],
                subject=send.subject or "",
                body_text=send.body_rendered or "",
                tags=[
                    {"name": "kind", "value": "outreach"},
                    {"name": "sequence_id", "value": str(send.sequence_id)},
                    {"name": "step_index", "value": str(send.step_index)},
                ],
            )
        except ResendApiError as e:
            send.status = OutreachSendStatus.FAILED
            ctx.session.flush()
            raise OutreachSenderError(f"Resend send falló: {e}") from e

        send.status = OutreachSendStatus.SENT
        send.sent_at = datetime.now(UTC)
        send.provider_message_id = result.message_id

        # Si la secuencia estaba READY y este es el primer envío exitoso,
        # promovemos a IN_PROGRESS.
        if seq.status == OutreachSequenceStatus.READY:
            seq.status = OutreachSequenceStatus.IN_PROGRESS

        ctx.session.add(
            AuditLog(
                actor="outreach-sender",
                action=AuditAction.SEND,
                entity_type="outreach_send",
                entity_id=str(send.id),
                legal_ground="6.1.f",
                payload={
                    "message_id": result.message_id,
                    "lead_id": lead.id,
                    "sequence_id": send.sequence_id,
                    "step_index": send.step_index,
                    "to": lead.emails[0],
                },
            )
        )
        ctx.session.flush()

        return AgentResult(
            summary=f"Send {send.id} enviado (message_id={result.message_id})",
            outputs={
                "send_id": send.id,
                "message_id": result.message_id,
                "sequence_id": seq.id,
                "sequence_status": seq.status.value,
            },
        )

    def _check_opted_out(self, ctx: AgentContext, emails: list[str]) -> str | None:
        stmt = select(OptOutLog.email).where(OptOutLog.email.in_(emails))
        row = ctx.session.execute(stmt).first()
        return row[0] if row else None
