"""ResendNotifierAgent — envío de notificaciones internas vía Resend.

Sólo envía a destinatarios `@webcafeina.com` (operadores del equipo). Nunca
a leads — ese flujo es OutreachSendDispatcher (otro agent, otro task).

Casos de uso:
- Avisar al operador asignado cuando un proyecto cambia a `failed`.
- Resumen diario del scoreboard de leads/migraciones.
- Notificar al equipo cuando llega una pregunta de un cliente vía webhook
  (Resend reply → audit_log entrada → notify).

Sin `RESEND_API_KEY` configurada devuelve summary "skipped" (igual que
ClickupSyncerAgent), de modo que el orchestrator puede seguir avanzando
en dev sin email.
"""

from __future__ import annotations

import logging
import os

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ResendNotifierError
from wcm_worker.integrations.resend import ResendApiError, ResendClient

log = logging.getLogger("wcm.worker.resend_notifier")

#: Dominio interno permitido. Cualquier destinatario que no termine aquí
#: se rechaza en `run` por seguridad — evita confundir notificaciones
#: internas con outreach a leads.
INTERNAL_DOMAIN = "@webcafeina.com"


class ResendNotifierAgent(BaseAgent):
    name = "resend-notifier"
    phase_name = "notify"

    def __init__(self, client: ResendClient | None = None) -> None:
        self._injected_client = client

    def run(self, ctx: AgentContext) -> AgentResult:
        recipients: list[str] = ctx.extra.get("recipients", [])
        subject: str = ctx.extra.get("subject", "")
        body_text: str = ctx.extra.get("body_text", "")
        body_html: str | None = ctx.extra.get("body_html")
        if not recipients or not subject or not body_text:
            raise ResendNotifierError(
                "ResendNotifierAgent requiere recipients, subject y body_text en ctx.extra"
            )

        for r in recipients:
            if not r.lower().endswith(INTERNAL_DOMAIN):
                raise ResendNotifierError(
                    f"Destinatario {r!r} no es interno (@webcafeina.com). "
                    "ResendNotifierAgent solo notifica al equipo."
                )

        client = self._injected_client or ResendClient.from_env()
        if client is None:
            log.info("resend_notify_skipped_no_credentials")
            return AgentResult(
                summary=f"Resend notify skipped (no RESEND_API_KEY) — {len(recipients)} destinatarios omitidos",
                outputs={"skipped": True, "would_send_to": recipients},
            )

        from_email = os.environ.get("RESEND_FROM_EMAIL", "migrator@webcafeina.com")
        try:
            result = client.send(
                to=recipients,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_email=from_email,
                tags=[{"name": "kind", "value": "internal_notification"}],
            )
        except ResendApiError as e:
            raise ResendNotifierError(f"Resend send falló: {e}") from e

        return AgentResult(
            summary=f"Notify enviada a {len(recipients)} destinatario(s) (message_id={result.message_id})",
            outputs={
                "message_id": result.message_id,
                "recipients": recipients,
                "status": result.status,
            },
        )
