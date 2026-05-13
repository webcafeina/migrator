"""ResendNotifier (stub). Implementación real en Fase 10."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class ResendNotifierAgent(BaseAgent):
    name = "resend-notifier"
    phase_name = "notify"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "ResendNotifierAgent: implementación real pendiente para Fase 10. "
            "Skill: resend-notifier. Solo envía a destinatarios internos @webcafeina.com "
            "(nunca a leads — eso es revisión humana via outreach-composer)."
        )
