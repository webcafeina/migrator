"""Prospector (stub).

Implementación real en **Fase 9 (Prospección)** cuando estén las
integraciones con Google Maps API + directory-scraper + dorks +
gdpr-compliance.

Por ahora levanta NotImplementedError. La task Celery
`wcm.prospector.run_campaign` puede llamar al stub para que el flujo de
encolado se valide aunque no se ejecute nada de prospección real.
"""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class ProspectorAgent(BaseAgent):
    name = "prospector"
    phase_name = "prospect"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "ProspectorAgent: implementación real pendiente para Fase 9. "
            "Skill docs: .claude/skills/{google-maps-scraper,directory-scraper,gdpr-compliance}/SKILL.md"
        )
