"""FormsRebuilder (stub). Recrea formularios origen como Gravity Forms."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class FormsRebuilderAgent(BaseAgent):
    name = "forms-rebuilder"
    phase_name = "rebuild_forms"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "FormsRebuilderAgent: implementación real pendiente. "
            "Skill: wp-rest-bulk (endpoint Gravity Forms /gf/v2/forms). "
            "Mapeo HTML5 input types → Gravity Forms field types documentado en agent .md."
        )
