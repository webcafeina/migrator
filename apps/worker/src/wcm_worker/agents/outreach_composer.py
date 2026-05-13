"""OutreachComposer (stub). Implementación real en Fase 9."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class OutreachComposerAgent(BaseAgent):
    name = "outreach-composer"
    phase_name = "compose_outreach"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "OutreachComposerAgent: implementación real pendiente para Fase 9. "
            "Skill: .claude/skills/gdpr-compliance/SKILL.md (validación legal LSSI-CE obligatoria)"
        )
