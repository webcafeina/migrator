"""WooMigrator (stub). Condicional: solo se invoca si project.has_ecommerce."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class WooMigratorAgent(BaseAgent):
    name = "woo-migrator"
    phase_name = "migrate_woo"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "WooMigratorAgent: implementación real pendiente. "
            "Skill: wp-rest-bulk (endpoints WooCommerce wc/v3). "
            "El orchestrator solo invoca este agent si project.has_ecommerce=True."
        )
