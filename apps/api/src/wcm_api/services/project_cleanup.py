"""Limpieza de objetos R2 al borrar un proyecto (ADR-054 tarea #101 — bug huérfano).

El borrado de un proyecto en BD elimina las filas por CASCADE pero las URLs
R2 referenciadas en `assets`, `visual_diffs`, `bricks_pages`, etc. quedaban
huérfanas consumiendo storage. Este helper centraliza la limpieza:

- Prefijo único `projects/{id}/` (convención del worker — todos los agents
  suben bajo este prefix). delete_prefix iterando paginado.
- Si R2 no está configurado → no-op (warning en log).
- Si delete_prefix falla → log warning pero NO levanta: prioridad es borrar
  el proyecto en BD; un huérfano R2 acumulable es preferible a un proyecto
  parcialmente borrado.
"""

from __future__ import annotations

import logging

log = logging.getLogger("wcm.api.project_cleanup")


def delete_project_r2_assets(project_id: int) -> dict[str, int | str]:
    """Borra todos los objetos R2 bajo `projects/{project_id}/`.

    Devuelve un dict con métricas para audit/log. Nunca levanta.
    """
    try:
        from wcm_worker.integrations.r2 import R2Client, R2UploadError
    except ImportError as e:
        log.warning(
            "project_cleanup_r2_import_failed",
            extra={"project_id": project_id, "error": str(e)},
        )
        return {"status": "skipped", "reason": "r2_import_failed", "deleted": 0}

    client = R2Client.from_env()
    if client is None:
        log.info(
            "project_cleanup_r2_not_configured",
            extra={"project_id": project_id},
        )
        return {"status": "skipped", "reason": "r2_not_configured", "deleted": 0}

    prefix = f"projects/{project_id}/"
    try:
        deleted = client.delete_prefix(prefix)
    except R2UploadError as e:
        log.warning(
            "project_cleanup_r2_delete_failed",
            extra={"project_id": project_id, "prefix": prefix, "error": str(e)},
        )
        return {"status": "error", "reason": str(e), "deleted": 0}

    log.info(
        "project_cleanup_r2_ok",
        extra={"project_id": project_id, "prefix": prefix, "deleted": deleted},
    )
    return {"status": "ok", "prefix": prefix, "deleted": deleted}
