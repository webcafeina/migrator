"""RedesignTemplatesAgent — pipeline templates Bricks (Sprint v0.25.0 B5).

STUB para que el pipeline canónico v0.25.0 incluya la fase. La
implementación real (SectionPicker + SlotMapper + ensamblado) se
completa en el Bloque B5.

Cuando `Project.design_method == 'templates'`:
1. Carga el `Brief` del proyecto.
2. Para cada `Brief.pages[i].sections[j]`:
   - `SectionPicker.choose(section, brief.business, sections_index)`
     → template Bricks de `docs/templates/brickstemplate/`.
   - `SlotMapper.apply(template_json, section, brief)` → árbol Bricks
     con placeholders rellenados.
3. Persiste resultado en `bricks_pages.bricks_json` igual que el
   legacy `transpile_bricks`.

MVP B5 (este bloque): stub que solo log + skip; el pipeline ya integra
la condition_callable que solo dispara este agente cuando design_method
es 'templates'.
"""

from __future__ import annotations

import logging

from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RedesignAgentError

log = logging.getLogger("wcm.worker.redesign_templates")


class RedesignTemplatesAgent(BaseAgent):
    name = "redesign-templates"
    phase_name = "redesign_templates"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("RedesignTemplatesAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")
        if project.design_method != "templates":
            return AgentResult(
                summary=(
                    f"Project {project.id}: design_method={project.design_method!r} "
                    "→ redesign_templates SKIPPED"
                ),
                outputs={"skipped": True, "reason": "design_method_mismatch"},
            )
        if not project.brief_json:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin brief_json → "
                    "redesign_templates SKIPPED (BriefGenerator no corrió)"
                ),
                outputs={"skipped": True, "reason": "no_brief"},
                warnings=["BriefGenerator debe correr antes de RedesignTemplates"],
            )
        # MVP B5: implementación real pendiente.
        log.warning(
            "redesign_templates_stub_invoked",
            extra={"project_id": project.id, "n_pages": len(project.brief_json.get("pages", []))},
        )
        return AgentResult(
            summary=(
                f"Project {project.id}: redesign_templates STUB "
                "(implementación pendiente en B5)"
            ),
            outputs={
                "skipped": True,
                "reason": "stub_b5_pending",
                "n_pages_in_brief": len(project.brief_json.get("pages", [])),
            },
            warnings=["Implementación real pendiente — Bloque B5."],
        )
