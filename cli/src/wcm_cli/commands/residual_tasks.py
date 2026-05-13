"""Comandos sobre tareas residuales (entregable humano)."""

from __future__ import annotations

from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient

app = typer.Typer(help="Tareas residuales del checklist humano")


@app.command("list")
def list_tasks(
    project_id: Annotated[int | None, typer.Option(help="Filtro por proyecto")] = None,
    category: Annotated[str | None, typer.Option(help="Filtro por categoría")] = None,
    status: Annotated[str | None, typer.Option(help="Filtro por status")] = None,
) -> None:
    """Lista tareas residuales con filtros."""
    params = {}
    if project_id is not None:
        params["project_id"] = project_id
    if category:
        params["category"] = category
    if status:
        params["status_filter"] = status

    client = ApiClient()
    tasks = client.get("/api/v1/residual-tasks", params=params)

    if not tasks:
        output.info("Sin tareas residuales.")
        return

    output.render_table(
        f"Tareas residuales ({len(tasks)})",
        ["id", "proyecto", "categoría", "título", "asignado", "minutos", "status"],
        [
            [
                t["id"], t["project_id"], t["category"],
                t["title"][:60],
                t.get("assignee_hint") or "—",
                t.get("estimated_minutes") or "—",
                t["status"],
            ]
            for t in tasks
        ],
        json_payload=tasks,
    )


@app.command("done")
def mark_done(task_id: Annotated[int, typer.Argument()]) -> None:
    """Marca una tarea residual como completada (sync a ClickUp)."""
    client = ApiClient()
    result = client.patch(
        f"/api/v1/residual-tasks/{task_id}/status",
        json={"status": "done"},
    )
    output.success(f"Tarea {task_id} marcada done — sync con ClickUp encolada")
    if output.is_json_mode():
        output.emit_json(result)
