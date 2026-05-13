"""QaRunner (stub). Lighthouse + W3C validator + link checker."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class QaRunnerAgent(BaseAgent):
    name = "qa-runner"
    phase_name = "qa"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "QaRunnerAgent: implementación real pendiente. "
            "Tooling: Lighthouse CLI (Node), validator.w3.org API, link checker propio, "
            "verificación de redirects 301, certificado SSL. Se implementa en Fase 10/14."
        )
