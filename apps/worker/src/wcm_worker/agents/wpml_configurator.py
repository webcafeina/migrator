"""WpmlConfigurator (stub). Condicional: solo se invoca si project.is_multilang."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class WpmlConfiguratorAgent(BaseAgent):
    name = "wpml-configurator"
    phase_name = "configure_wpml"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "WpmlConfiguratorAgent: implementación real pendiente. "
            "Skills: wp-rest-bulk + wpcli-ssh para `wp wpml lang`. "
            "El orchestrator solo invoca este agent si project.is_multilang=True (ADR-003)."
        )
