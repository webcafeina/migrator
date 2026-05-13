"""VisualDiff (stub). Requiere Playwright + pixelmatch."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class VisualDiffAgent(BaseAgent):
    name = "visual-diff"
    phase_name = "visual_diff"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "VisualDiffAgent: implementación real pendiente. "
            "Skill: visual-diff-pixelmatch. Requiere Playwright + binarios pixelmatch. "
            "En MVP el orchestrator omite esta fase si no hay Playwright instalado."
        )
