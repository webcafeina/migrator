"""RedesignAIAgent — pipeline AI generativo OpenAI gpt-4o (Sprint v0.25.0 B6).

STUB para que el pipeline canónico v0.25.0 incluya la fase. La
implementación real (OpenAI tool_use + few-shot h2b + validación schema
+ retry + fallback templates) se completa en el Bloque B6.

Cuando `Project.design_method == 'ai'`:
1. Carga el `Brief` del proyecto.
2. Por cada `Brief.pages[i]`:
   - `OpenAIClient.generate_page_redesign(brief, page_spec)` con
     `tool_use=emit_bricks_page`.
   - Valida output contra `wcm_bricks_transpiler.schema`.
   - 1 retry con error context si falla.
   - Fallback a `RedesignTemplatesAgent.regenerate_page()` si retry falla.
3. Persiste resultado en `bricks_pages.bricks_json`.
"""

from __future__ import annotations

import logging

from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RedesignAgentError

log = logging.getLogger("wcm.worker.redesign_ai")


class RedesignAIAgent(BaseAgent):
    name = "redesign-ai"
    phase_name = "redesign_ai"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("RedesignAIAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")
        if project.design_method != "ai":
            return AgentResult(
                summary=(
                    f"Project {project.id}: design_method={project.design_method!r} "
                    "→ redesign_ai SKIPPED"
                ),
                outputs={"skipped": True, "reason": "design_method_mismatch"},
            )
        if not project.brief_json:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin brief_json → "
                    "redesign_ai SKIPPED (BriefGenerator no corrió)"
                ),
                outputs={"skipped": True, "reason": "no_brief"},
                warnings=["BriefGenerator debe correr antes de RedesignAI"],
            )
        # MVP B6: implementación real pendiente.
        log.warning(
            "redesign_ai_stub_invoked",
            extra={"project_id": project.id, "n_pages": len(project.brief_json.get("pages", []))},
        )
        return AgentResult(
            summary=(
                f"Project {project.id}: redesign_ai STUB "
                "(implementación pendiente en B6)"
            ),
            outputs={
                "skipped": True,
                "reason": "stub_b6_pending",
                "n_pages_in_brief": len(project.brief_json.get("pages", [])),
            },
            warnings=["Implementación real pendiente — Bloque B6."],
        )
