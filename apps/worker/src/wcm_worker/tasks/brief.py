"""Tasks Celery del bloque Brief refinement (Sprint v0.27.0 B5).

Encoladas por endpoints `/projects/{id}/brief/suggest-refinements`.
Invocan `BriefRefinementAgent` que persiste las propuestas en
`Project.brief_refinement_proposals_json`.
"""

from __future__ import annotations

import logging
from typing import Any

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.brief_refinement import BriefRefinementAgent
from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope
from wcm_worker.integrations.events import publish_phase_event

log = logging.getLogger("wcm.worker.tasks.brief")


@celery_app.task(name="wcm.brief.suggest_refinements", bind=True, max_retries=0)
def run_suggest_refinements(self, project_id: int) -> dict[str, Any]:
    """Encola la generación de propuestas de mejora del Brief con AI.

    Es un agente reactivo (no parte del pipeline canónico). El
    operador lo dispara desde el dashboard `/preview` → "🪄 Sugerir
    mejoras (AI)".

    Resultado persistido en `Project.brief_refinement_proposals_json`.
    El dashboard luego refresca y pinta las propuestas en el panel
    lateral.
    """
    log.info(
        "brief_suggest_refinements_start",
        extra={"project_id": project_id},
    )
    publish_phase_event(
        project_id,
        "brief_refinement",
        "running",
        summary="Generando propuestas de mejora con AI",
    )

    with session_scope() as session:
        ctx = AgentContext(session=session, project_id=project_id)
        try:
            result = BriefRefinementAgent().run(ctx)
        except Exception as e:  # noqa: BLE001
            log.exception(
                "brief_suggest_refinements_failed",
                extra={"project_id": project_id},
            )
            publish_phase_event(
                project_id, "brief_refinement",
                "failed", summary=f"{type(e).__name__}: {e}",
            )
            raise
        session.flush()

    publish_phase_event(
        project_id, "brief_refinement",
        "completed", summary=result.summary,
    )

    return {
        "project_id": project_id,
        "status": "completed",
        "summary": result.summary,
        "outputs": result.outputs,
    }
