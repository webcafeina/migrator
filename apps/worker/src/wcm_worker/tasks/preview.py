"""Task Celery `wcm.preview.regenerate_page` (Sprint v0.25.1 B7).

Encolada por el API `POST /api/v1/projects/{id}/preview/regenerate-page`.
Re-ejecuta el agente de rediseño apropiado (RedesignTemplates o
RedesignAI según `Project.design_method`) **SOLO para 1 página** del
Brief, sin tocar las demás.

Estrategia:
1. Guarda referencia al brief original.
2. Sustituye temporalmente `project.brief_json["pages"]` por solo la
   página solicitada.
3. Invoca el agente.
4. Restaura el brief original.
5. Persiste el `bricks_pages.bricks_json` regenerado (el agente ya
   hace UPSERT por slug, así que la página actualizada se persiste OK).

Idempotente: el operador puede regenerar la misma página N veces.
Cada call genera una versión nueva (templates es determinista por
hash, AI puede dar variaciones).
"""

from __future__ import annotations

import logging
from typing import Any

from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.redesign_ai import RedesignAIAgent
from wcm_worker.agents.redesign_templates import RedesignTemplatesAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.integrations.events import publish_phase_event

log = logging.getLogger("wcm.worker.tasks.preview")


@celery_app.task(name="wcm.preview.regenerate_page", bind=True, max_retries=0)
def run_regenerate_page(self, project_id: int, slug: str) -> dict[str, Any]:
    """Re-ejecuta el agente de rediseño solo para una página.

    `slug` debe matchear `Brief.pages[i].slug`. Si no encontrado en
    el Brief, devuelve `not_found_in_brief`.
    """
    log.info(
        "preview_regenerate_page_start",
        extra={"project_id": project_id, "slug": slug},
    )
    publish_phase_event(
        project_id,
        f"preview_regenerate_{slug}",
        "running",
        summary=f"Regenerando página {slug}",
    )

    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            return {"project_id": project_id, "status": "not_found"}
        if not project.brief_json or not project.brief_json.get("pages"):
            return {
                "project_id": project_id,
                "status": "no_brief",
                "warning": "BriefGenerator no corrió o el brief está vacío.",
            }

        # Buscar página en el brief.
        original_brief = project.brief_json
        original_pages = original_brief.get("pages") or []
        target_page = next(
            (p for p in original_pages if p.get("slug") == slug),
            None,
        )
        if target_page is None:
            return {
                "project_id": project_id,
                "status": "not_found_in_brief",
                "slug": slug,
                "available_slugs": [p.get("slug") for p in original_pages],
            }

        # Sustituir brief.pages temporalmente con solo la página objetivo.
        mini_brief = {**original_brief, "pages": [target_page]}
        project.brief_json = mini_brief
        session.flush()

        try:
            agent: Any
            if project.design_method == "ai":
                agent = RedesignAIAgent()
            elif project.design_method == "templates":
                agent = RedesignTemplatesAgent()
            else:
                # Legacy proyecto v0.24.0 — no aplicable a preview.
                return {
                    "project_id": project_id,
                    "status": "legacy_design_method",
                    "warning": (
                        f"design_method={project.design_method!r} no soporta "
                        "regenerate-page. Re-lanzar pipeline completo."
                    ),
                }

            ctx = AgentContext(session=session, project_id=project_id)
            try:
                result = agent.run(ctx)
            except Exception as e:  # noqa: BLE001
                log.exception(
                    "preview_regenerate_page_agent_failed",
                    extra={"project_id": project_id, "slug": slug},
                )
                publish_phase_event(
                    project_id, f"preview_regenerate_{slug}",
                    "failed", summary=f"{type(e).__name__}: {e}",
                )
                # Restaurar brief antes de re-raise.
                project.brief_json = original_brief
                session.flush()
                raise

            session.flush()
        finally:
            # SIEMPRE restaurar brief original.
            project.brief_json = original_brief
            session.flush()

        publish_phase_event(
            project_id, f"preview_regenerate_{slug}",
            "completed", summary=result.summary,
        )

    return {
        "project_id": project_id,
        "status": "regenerated",
        "slug": slug,
        "design_method": project.design_method,
        "summary": result.summary,
        "outputs": result.outputs,
    }
