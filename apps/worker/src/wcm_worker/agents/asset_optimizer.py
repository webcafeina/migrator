"""AssetOptimizer (stub). Implementación real en Fase 10 (integración R2)."""

from __future__ import annotations

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AgentNotImplementedError


class AssetOptimizerAgent(BaseAgent):
    name = "asset-optimizer"
    phase_name = "optimize_assets"

    def run(self, ctx: AgentContext) -> AgentResult:
        raise AgentNotImplementedError(
            "AssetOptimizerAgent: implementación real pendiente para Fase 10. "
            "Skills: image-pipeline (Pillow + cwebp), r2-uploader (Cloudflare R2). "
            "Mientras: los assets se referencian desde su URL original."
        )
