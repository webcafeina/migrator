"""ClickupSyncer (stub). Implementación real en Fase 10."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class ClickupSyncerAgent(BaseAgent):
    name = "clickup-syncer"
    phase_name = "sync_clickup"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "ClickupSyncerAgent: implementación real pendiente para Fase 10. "
            "Skill: clickup-task-creator. Team ID 20483773, lista Microtareas 900102088242."
        )
