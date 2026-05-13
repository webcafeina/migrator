"""ChecklistGenerator (stub). WeasyPrint para PDF; en MVP solo MD."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class ChecklistGeneratorAgent(BaseAgent):
    name = "checklist-generator"
    phase_name = "generate_checklist"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "ChecklistGeneratorAgent: implementación real pendiente. "
            "Lee residual_tasks del proyecto y produce checklist-<id>.md + .pdf "
            "(WeasyPrint con paleta Webcafeína). Se implementa en Fase 10 (integraciones) "
            "o Fase 14 (documentación) según prioridad."
        )
