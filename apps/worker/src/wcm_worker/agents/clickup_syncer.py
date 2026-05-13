"""ClickupSyncerAgent — sincroniza residual_tasks ↔ ClickUp.

Modo de operación (Fase 10):
- Para cada `ResidualTask` del proyecto sin `clickup_task_id`: crea task
  en ClickUp y persiste el id devuelto.
- Para cada `ResidualTask` con `clickup_task_id` y `status != DONE`:
  actualiza title/description si cambiaron (idempotente).
- Para cada `ResidualTask` con `status=DONE` y `clickup_task_id`:
  marca cerrada en ClickUp si no lo estaba ya.

Sin credenciales (`CLICKUP_API_TOKEN` vacío) devuelve summary "skipped"
y no toca la BD. Esto permite que el pipeline siga avanzando en dev.

Mapping de prioridades:
- BLOCKING_GO_LIVE → urgent (1)
- CLIENT_CONFIG → high (2)
- VISUAL_CONTENT → normal (3)
- POST_GO_LIVE → low (4)
- OTHER → normal (3)
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from wcm_db.models.audit import AuditLog
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import AuditAction, ResidualCategory, ResidualStatus

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ClickupSyncerError
from wcm_worker.integrations.clickup import ClickupApiError, ClickupClient

log = logging.getLogger("wcm.worker.clickup_syncer")

_PRIORITY_BY_CATEGORY: dict[ResidualCategory, int] = {
    ResidualCategory.BLOCKING_GO_LIVE: 1,
    ResidualCategory.CLIENT_CONFIG: 2,
    ResidualCategory.VISUAL_CONTENT: 3,
    ResidualCategory.POST_GO_LIVE: 4,
    ResidualCategory.OTHER: 3,
}


class ClickupSyncerAgent(BaseAgent):
    name = "clickup-syncer"
    phase_name = "sync_clickup"

    def __init__(self, client: ClickupClient | None = None) -> None:
        """`client` inyectable para tests. En prod se construye desde env."""
        self._injected_client = client

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise ClickupSyncerError("ClickupSyncerAgent requiere project_id")

        client = self._injected_client or ClickupClient.from_env()
        if client is None:
            log.info("clickup_sync_skipped_no_credentials")
            return AgentResult(
                summary="ClickUp sync skipped (no CLICKUP_API_TOKEN)",
                outputs={"skipped": True},
            )

        residuals = self._load_residuals(ctx, ctx.project_id)
        if not residuals:
            return AgentResult(
                summary=f"Proyecto {ctx.project_id}: 0 tareas residuales",
                outputs={"created": 0, "updated": 0, "closed": 0},
            )

        created = updated = closed = errors = 0
        warnings: list[str] = []

        for residual in residuals:
            try:
                action = self._sync_one(client, residual)
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                elif action == "closed":
                    closed += 1
            except ClickupApiError as e:
                errors += 1
                msg = f"residual {residual.id}: {e}"
                log.warning(
                    "clickup_sync_residual_failed",
                    extra={"residual_id": residual.id, "error": str(e)},
                )
                warnings.append(msg)

        ctx.session.add(
            AuditLog(
                actor="clickup-syncer",
                action=AuditAction.UPDATE,
                entity_type="project",
                entity_id=str(ctx.project_id),
                payload={
                    "created": created,
                    "updated": updated,
                    "closed": closed,
                    "errors": errors,
                },
            )
        )
        ctx.session.flush()

        if self._injected_client is None:
            client.close()

        return AgentResult(
            summary=f"Project {ctx.project_id}: +{created} new / {updated} updated / "
            f"{closed} closed / {errors} errors",
            outputs={
                "created": created,
                "updated": updated,
                "closed": closed,
                "errors": errors,
            },
            warnings=warnings,
        )

    # ---------- helpers ----------

    def _load_residuals(self, ctx: AgentContext, project_id: int) -> list[ResidualTask]:
        stmt = select(ResidualTask).where(ResidualTask.project_id == project_id)
        return list(ctx.session.execute(stmt).scalars())

    def _sync_one(self, client: ClickupClient, residual: ResidualTask) -> str:
        """Devuelve la acción realizada: 'created', 'updated', 'closed'."""
        priority = _PRIORITY_BY_CATEGORY.get(residual.category, 3)
        body = _build_description(residual)

        if residual.clickup_task_id is None:
            assignees: list[int] = []
            if residual.assignee_hint:
                user_id = client.find_member(residual.assignee_hint)
                if user_id:
                    assignees.append(user_id)
            task = client.create_task(
                title=residual.title,
                description=body,
                priority=priority,
                assignees=assignees or None,
                tags=[residual.category.value, f"wcm-residual-{residual.id}"],
            )
            residual.clickup_task_id = str(task.get("id"))
            return "created"

        if residual.status == ResidualStatus.DONE:
            client.close_task(residual.clickup_task_id)
            return "closed"

        client.update_task(
            residual.clickup_task_id,
            name=residual.title,
            description=body,
            priority=priority,
        )
        return "updated"


def _build_description(residual: ResidualTask) -> str:
    """Construye el body Markdown del task ClickUp."""
    parts = [residual.description.rstrip(), "", "---"]
    parts.append(f"**Categoría**: {residual.category.value}")
    if residual.estimated_minutes:
        parts.append(f"**Tiempo estimado**: {residual.estimated_minutes} min")
    if residual.generated_by:
        parts.append(f"**Generada por**: `{residual.generated_by}`")
    if residual.screenshot_paths:
        parts.append("")
        parts.append("**Capturas**:")
        for p in residual.screenshot_paths:
            parts.append(f"- {p}")
    parts.append("")
    parts.append(f"_Mantenida por Webcafeína Migrator (residual_task #{residual.id})_")
    return "\n".join(parts)
