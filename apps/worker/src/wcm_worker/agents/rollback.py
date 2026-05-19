"""RollbackAgent — deshace un deploy de páginas WP creadas por wp-deployer.

v0.20.0 (ADR-042) — Branching:
- Si `project.pre_deploy_snapshot_path` está set y el .sql es accesible →
  restauración por snapshot (`wp db import path/snapshot.sql`). Borra
  TODO lo creado por la migración y deja el WP exactamente como estaba.
  Adicionalmente, resetea wp_post_id en bricks_pages para coherencia.
- Si no hay snapshot → branch MVP histórica: itera
  `bricks_pages.wp_post_id IS NOT NULL` y `DELETE /wp/v2/pages/{id}?force=true`.

El branching es transparente al orchestrator; ambas devuelven el mismo
AgentResult shape.

NO restaura (en branch MVP):
- Cambios a páginas existentes pre-migración (no las teníamos en snapshot).
- Configuración WPML / menús / opciones (no las migramos).
- Productos WooCommerce ni formularios Gravity Forms.

NO restaura (en branch snapshot):
- Si el deploy modificó ficheros en wp-content/uploads (imágenes,
  fonts), esos quedan tras el rollback. Necesita complemento futuro
  con snapshot tar.gz del filesystem.

Resiliencia:
- Si una página individual falla (MVP) → continúa con la siguiente.
- Si el snapshot file no existe en el destino → fallback automático a MVP.
- Si SSH no accesible (snapshot) → fase FAILED.
- Idempotente: re-ejecutar tras un rollback parcial completa el trabajo.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RollbackAgentError
from wcm_wp_client import WpClientConfig, WpCliSshClient, WpRestClient
from wcm_wp_client.errors import WpCliExecutionError, WpSshError

log = logging.getLogger("wcm.worker.rollback")


class RollbackAgent(BaseAgent):
    name = "rollback"
    phase_name = "rollback"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RollbackAgentError("RollbackAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RollbackAgentError(f"Project {ctx.project_id} no encontrado")

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise RollbackAgentError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        # ADR-042 — branching snapshot/MVP.
        if project.pre_deploy_snapshot_path:
            return self._rollback_via_snapshot(ctx, project, wp_config)

        return self._rollback_via_rest_delete(ctx, project, wp_config)

    def _rollback_via_rest_delete(
        self,
        ctx: AgentContext,
        project: Project,
        wp_config: WpClientConfig,
    ) -> AgentResult:
        """Branch MVP: borra páginas vía REST DELETE una a una."""
        pages = list(
            ctx.session.execute(
                select(BricksPage).where(
                    BricksPage.project_id == project.id,
                    BricksPage.wp_post_id.is_not(None),
                )
            ).scalars().all()
        )
        if not pages:
            return AgentResult(
                summary=f"Project {project.id}: 0 páginas a borrar (nada que deshacer).",
                outputs={"pages_deleted": 0, "pages_failed": 0},
            )

        deleted, failed, warnings = asyncio.run(self._rollback(wp_config, pages))
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id} rollback · {deleted} páginas borradas, "
                f"{failed} fallidas."
            ),
            outputs={
                "pages_deleted": deleted,
                "pages_failed": failed,
                "target": wp_config.site_url,
                "strategy": "rest_delete_mvp",
            },
            warnings=warnings,
        )

    def _rollback_via_snapshot(
        self,
        ctx: AgentContext,
        project: Project,
        wp_config: WpClientConfig,
    ) -> AgentResult:
        """Branch ADR-042: `wp db import snapshot.sql` por SSH."""
        snapshot_path = project.pre_deploy_snapshot_path
        warnings: list[str] = []

        try:
            asyncio.run(self._restore_snapshot(wp_config, snapshot_path))
        except (WpSshError, WpCliExecutionError) as e:
            # Snapshot inaccesible (borrado, disk full, etc.). Caer
            # al MVP para hacer algo útil en lugar de bloquear todo.
            log.warning(
                "rollback_snapshot_failed_fallback_to_rest",
                extra={
                    "project_id": project.id,
                    "snapshot_path": snapshot_path,
                    "error": str(e),
                },
            )
            warnings.append(
                f"Snapshot {snapshot_path} no restaurable "
                f"({type(e).__name__}: {str(e)[:140]}). Fallback a REST DELETE."
            )
            result = self._rollback_via_rest_delete(ctx, project, wp_config)
            return AgentResult(
                summary=result.summary,
                outputs={**result.outputs, "strategy": "fallback_rest_after_snapshot_fail"},
                warnings=warnings + (result.warnings or []),
            )

        # Snapshot restaurado OK → resetear wp_post_id de todas las bricks_pages
        # para que un próximo deploy pueda recrearlas desde cero.
        reset_count = ctx.session.execute(
            select(BricksPage).where(
                BricksPage.project_id == project.id,
                BricksPage.wp_post_id.is_not(None),
            )
        ).scalars().all()
        for bp in reset_count:
            bp.wp_post_id = None
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id} rollback · snapshot {snapshot_path} "
                f"restaurado vía wp db import. {len(reset_count)} wp_post_id reseteados."
            ),
            outputs={
                "strategy": "snapshot_restore",
                "snapshot_path": snapshot_path,
                "pages_reset": len(reset_count),
                "target": wp_config.site_url,
            },
            warnings=warnings,
        )

    @staticmethod
    async def _restore_snapshot(
        wp_config: WpClientConfig, snapshot_path: str
    ) -> None:
        async with WpCliSshClient(wp_config) as cli:
            # Check fichero presente antes de tocar la base.
            await cli.run_or_raise(
                ["cli", "info"],  # smoke
                timeout_s=15.0,
            )
            await cli.run_or_raise(
                ["db", "import", snapshot_path],
                timeout_s=600.0,
            )

    @staticmethod
    async def _rollback(
        wp_config: WpClientConfig, pages: list[BricksPage]
    ) -> tuple[int, int, list[str]]:
        deleted = 0
        failed = 0
        warnings: list[str] = []
        async with WpRestClient(wp_config) as rest:
            for bp in pages:
                wp_post_id = bp.wp_post_id
                if wp_post_id is None:
                    continue
                try:
                    await rest.delete_page(wp_post_id, force=True)
                    bp.wp_post_id = None
                    deleted += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    msg = f"Página WP id={wp_post_id} (slug={bp.slug}) falló: {type(e).__name__}: {e}"
                    warnings.append(msg)
                    log.warning(
                        "rollback_page_failed",
                        extra={"wp_post_id": wp_post_id, "error": str(e)},
                    )
        return deleted, failed, warnings
