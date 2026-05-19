"""PreDeploySnapshotAgent — snapshot SQL del WP destino antes de wp_deployer (ADR-042, v0.20.0+).

Ejecuta `wp db export` por SSH y deja un fichero `.sql` con timestamp en
`/var/backups/wcm-snapshots/project-{id}-{ts}.sql`. Persiste la ruta y la
hora en `projects.pre_deploy_snapshot_path/at`.

Esta fase se inserta antes de `wp_deployer`. Si el WP destino aún no
contiene contenido (instalación fresca), el snapshot es prácticamente
vacío — no pasa nada, sirve igualmente como punto de retorno.

Resiliencia:
- SSH no accesible → PreDeploySnapshotError (bloquea pipeline — el rollback
  posterior no podría operar sin snapshot).
- Disco lleno en destino → wp_cli fallaría con exit != 0 → error tipado.
- Idempotente: re-ejecutar genera un snapshot nuevo (timestamp distinto).
  El operador puede limpiar viejos con `wcm snapshots cleanup --older 30d`
  cuando exista (no en MVP).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import PreDeploySnapshotError
from wcm_wp_client import WpClientConfig, WpCliSshClient
from wcm_wp_client.errors import WpCliExecutionError, WpSshError

log = logging.getLogger("wcm.worker.pre_deploy_snapshot")

SNAPSHOT_DIR = "/var/backups/wcm-snapshots"


class PreDeploySnapshotAgent(BaseAgent):
    name = "pre-deploy-snapshot"
    phase_name = "pre_deploy_snapshot"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise PreDeploySnapshotError(
                "PreDeploySnapshotAgent requiere project_id"
            )
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise PreDeploySnapshotError(
                f"Project {ctx.project_id} no encontrado"
            )

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise PreDeploySnapshotError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        snapshot_path = f"{SNAPSHOT_DIR}/project-{project.id}-{ts}.sql"

        try:
            asyncio.run(self._snapshot(wp_config, snapshot_path))
        except (WpSshError, WpCliExecutionError) as e:
            raise PreDeploySnapshotError(
                f"Snapshot SQL falló para project {project.id}: "
                f"{type(e).__name__}: {e}"
            ) from e

        project.pre_deploy_snapshot_path = snapshot_path
        project.pre_deploy_snapshot_at = datetime.now(UTC)
        ctx.session.flush()

        log.info(
            "pre_deploy_snapshot_ok",
            extra={
                "project_id": project.id,
                "path": snapshot_path,
                "site_url": wp_config.site_url,
            },
        )

        return AgentResult(
            summary=(
                f"Project {project.id}: snapshot SQL guardado en {snapshot_path} "
                f"(target {wp_config.site_url})."
            ),
            outputs={
                "snapshot_path": snapshot_path,
                "snapshot_at": project.pre_deploy_snapshot_at.isoformat(),
            },
        )

    @staticmethod
    async def _snapshot(wp_config: WpClientConfig, snapshot_path: str) -> None:
        """Ejecuta `mkdir -p` + `wp db export` por SSH."""
        async with WpCliSshClient(wp_config) as cli:
            await cli.run_or_raise(
                ["cli", "info"],  # smoke check: WP-CLI alcanzable
                timeout_s=15.0,
            )
            await cli.run_or_raise(
                ["db", "export", snapshot_path],
                timeout_s=300.0,  # bases medianas tardan minutos
            )
