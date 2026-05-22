"""BriefRefinementAgent — propuestas de mejora del Brief con AI (v0.27.0 B2).

Agente reactivo (no en el pipeline canónico). Lo encola el endpoint
`POST /projects/{id}/brief/suggest-refinements` cuando el operador
hace click desde el dashboard `/preview`. NO modifica `Project.brief_json`
— solo persiste las propuestas en `Project.brief_refinement_proposals_json`.

Las propuestas se aplican una a una vía `POST /brief/apply-refinement`,
con opción de "Aplicar al Brief" (no regenerar) o "Aplicar + regenerar"
(encola `wcm.preview.regenerate_page` para la página afectada).

Flujo:
1. Carga `Project.brief_json` + `bricks_pages` del proyecto.
2. Construye `pages_summary` compacto (sin bricks_json crudo):
   `[{slug, intent, sections: [{type, design_method, headline, has_image}]}]`.
3. Llama `OpenAIClient.generate_brief_refinement(brief, pages_summary)`.
4. Persiste resultado en `Project.brief_refinement_proposals_json`:
   `{generated_at, model, cost_usd, proposals: [...]}`.

Sin `OPENAI_API_KEY` → SKIPPED + warning.
Sin Brief → SKIPPED.

Errores tipados: `BriefRefinementError(blocks_pipeline=False)`. Si
OpenAI falla → la última batch existente queda intacta.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import (
    BriefRefinementError,
    OpenAIClientError,
    OpenAIInvalidOutputError,
)
from wcm_worker.integrations.openai_client import OpenAIClient

log = logging.getLogger("wcm.worker.brief_refinement")


class BriefRefinementAgent(BaseAgent):
    name = "brief-refinement"
    phase_name = "brief_refinement"

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
    ) -> None:
        self._injected_client = openai_client

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise BriefRefinementError("BriefRefinementAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise BriefRefinementError(f"Project {ctx.project_id} no existe")

        brief = project.brief_json
        if not brief or not brief.get("pages"):
            return AgentResult(
                summary=f"Project {project.id}: sin brief_json → SKIPPED",
                outputs={"skipped": True, "reason": "no_brief"},
            )

        client = self._injected_client or OpenAIClient.from_env()
        if client is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin OPENAI_API_KEY → SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_openai_key"},
                warnings=[
                    "Configurar OPENAI_API_KEY para activar Brief refinement."
                ],
            )

        # Cargar bricks_pages para construir pages_summary.
        bp_stmt = select(BricksPage).where(BricksPage.project_id == project.id)
        bricks_pages = list(ctx.session.execute(bp_stmt).scalars())
        bp_by_slug = {bp.slug: bp for bp in bricks_pages}

        pages_summary = self._build_pages_summary(brief, bp_by_slug)

        try:
            result = asyncio.run(
                client.generate_brief_refinement(
                    brief=brief, pages_summary=pages_summary,
                )
            )
        except (OpenAIInvalidOutputError, OpenAIClientError) as e:
            log.warning(
                "brief_refinement_openai_failed",
                extra={"project_id": project.id, "error": str(e)[:200]},
            )
            return AgentResult(
                summary=(
                    f"Project {project.id}: OpenAI falló → propuestas "
                    "anteriores intactas."
                ),
                outputs={"skipped": True, "reason": "openai_failed"},
                warnings=[f"OpenAI: {str(e)[:200]}"],
            )

        proposals = (result.data or {}).get("proposals") or []
        # Inyecta applied_at: None para cada propuesta (operador apply tracking).
        normalized = [
            {**p, "applied_at": None} for p in proposals
        ]

        project.brief_refinement_proposals_json = {
            "generated_at": datetime.now(UTC).isoformat(),
            "model": result.model,
            "cost_usd": float(result.cost_usd),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "proposals": normalized,
        }
        flag_modified(project, "brief_refinement_proposals_json")
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: brief refinement · "
                f"{len(normalized)} propuestas · "
                f"coste ${float(result.cost_usd):.4f}"
            ),
            outputs={
                "skipped": False,
                "proposals_count": len(normalized),
                "cost_usd": float(result.cost_usd),
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "model": result.model,
            },
        )

    @staticmethod
    def _build_pages_summary(
        brief: dict[str, Any],
        bp_by_slug: dict[str, BricksPage],
    ) -> list[dict[str, Any]]:
        """Construye el resumen compacto que se manda al LLM.

        Sin bricks_json crudo (sería muy grande). Solo metadata
        accionable: slug, intent, y por cada sección type + design_method
        + headline (si existe) + has_image.
        """
        summary: list[dict[str, Any]] = []
        for page in brief.get("pages") or []:
            slug = page.get("slug") or "/"
            bp = bp_by_slug.get(slug)
            sections_summary: list[dict[str, Any]] = []
            for section in page.get("sections") or []:
                sec: dict[str, Any] = {
                    "type": section.get("type"),
                    "design_method": section.get("design_method"),
                }
                # Copia solo keys textuales útiles (para que el LLM
                # razone sobre copy y CTAs sin verse abrumado).
                for k in ("headline", "subheadline", "text", "cta_text", "cta_url"):
                    if section.get(k):
                        sec[k] = section[k]
                sec["has_image"] = bool(
                    section.get("asset_id") or section.get("image_url")
                )
                sections_summary.append(sec)
            summary.append({
                "slug": slug,
                "title": page.get("title"),
                "intent": page.get("intent"),
                "deployed_to_wp": bool(bp and bp.wp_post_id),
                "sections": sections_summary,
            })
        return summary
