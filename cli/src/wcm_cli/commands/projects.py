"""Comandos sobre proyectos de migración."""

from __future__ import annotations

from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient

app = typer.Typer(help="Proyectos de migración")


@app.command("list")
def list_projects(
    status: Annotated[str | None, typer.Option(help="Filtro por status")] = None,
) -> None:
    """Lista proyectos."""
    params = {}
    if status:
        params["project_status"] = status
    client = ApiClient()
    projects = client.get("/api/v1/projects", params=params)

    if not projects:
        output.info("Sin proyectos.")
        return

    output.render_table(
        f"Proyectos ({len(projects)})",
        ["id", "cliente", "origen", "destino", "builder", "status", "go_live"],
        [
            [
                p["id"],
                p["client_name"],
                p["source_url"],
                p.get("target_domain") or "—",
                p.get("builder_source") or "—",
                p["status"],
                p.get("estimated_go_live_at") or "—",
            ]
            for p in projects
        ],
        json_payload=projects,
    )


@app.command("get")
def get_project(project_id: Annotated[int, typer.Argument()]) -> None:
    """Detalle completo de un proyecto + sus fases."""
    client = ApiClient()
    project = client.get(f"/api/v1/projects/{project_id}")
    phases = client.get(f"/api/v1/projects/{project_id}/phases")

    if output.is_json_mode():
        output.emit_json({"project": project, "phases": phases})
        return

    output.header(f"Proyecto #{project_id} — {project['client_name']}")
    output.key_value({
        "origen": project["source_url"],
        "destino": project.get("target_domain") or "—",
        "builder": project.get("builder_source") or "—",
        "ecommerce": project["has_ecommerce"],
        "multilang": f"{project['is_multilang']} {project.get('langs') or []}",
        "status": project["status"],
        "iniciado": project.get("started_at") or "—",
        "completado": project.get("completed_at") or "—",
        "visual_diff_avg": project.get("visual_diff_avg_score") or "—",
    })

    if phases:
        output.render_table(
            "Fases",
            ["fase", "status", "intento", "started", "completed", "summary"],
            [
                [
                    p["phase_name"], p["status"], p["attempt"],
                    p.get("started_at") or "—",
                    p.get("completed_at") or "—",
                    (p.get("output_summary") or {}).get("summary", "—")[:60],
                ]
                for p in phases
            ],
        )


@app.command("status")
def status_project(project_id: Annotated[int, typer.Argument()]) -> None:
    """Alias breve de `wcm projects get`."""
    get_project(project_id)


@app.command("new")
def new_project(
    source: Annotated[str, typer.Option(help="URL origen de la web a migrar")],
    client_name: Annotated[str, typer.Option("--client", help="Nombre del cliente")],
    ecommerce: Annotated[bool, typer.Option(help="Activar pipeline WooCommerce")] = False,
    multilang: Annotated[bool, typer.Option(help="Activar pipeline WPML")] = False,
) -> None:
    """Crea un proyecto nuevo y opcionalmente lo arranca."""
    client = ApiClient()
    payload = {
        "client_name": client_name,
        "source_url": source,
        "has_ecommerce": ecommerce,
        "is_multilang": multilang,
    }
    project = client.post("/api/v1/projects", json=payload)
    output.success(f"Proyecto creado: #{project['id']} ({project['client_name']})")
    if output.is_json_mode():
        output.emit_json(project)
    else:
        output.info(
            f"Para arrancar el pipeline: [accent]wcm projects start {project['id']}[/]"
        )


@app.command("start")
def start_project(project_id: Annotated[int, typer.Argument()]) -> None:
    """Arranca el pipeline de migración (encola worker)."""
    client = ApiClient()
    result = client.post(f"/api/v1/projects/{project_id}/start")
    output.success(f"Pipeline encolado: task {result['task_id']}")
    output.info(f"Sigue el estado con: [accent]wcm projects get {project_id}[/]")


@app.command("resume")
def resume_project(project_id: Annotated[int, typer.Argument()]) -> None:
    """Reanuda un proyecto bloqueado/fallido."""
    client = ApiClient()
    result = client.post(f"/api/v1/projects/{project_id}/resume")
    output.success(f"Resume encolado: task {result['task_id']}")


@app.command("cancel")
def cancel_project(project_id: Annotated[int, typer.Argument()]) -> None:
    """Cancela un proyecto (no interrumpe el job en vuelo)."""
    client = ApiClient()
    client.post(f"/api/v1/projects/{project_id}/cancel")
    output.success(f"Proyecto {project_id} marcado como cancelled")


@app.command("export-checklist")
def export_checklist(
    project_id: Annotated[int, typer.Argument()],
    output_path: Annotated[str, typer.Option("--out", help="Ruta de salida")] = "./checklist.md",
) -> None:
    """Exporta el checklist humano del proyecto."""
    output.warning(
        "Export-checklist depende de ChecklistGeneratorAgent (stub en Fase 6)."
    )
    output.info(
        "La implementación real (WeasyPrint MD+PDF) llega en Fase 10/14. "
        f"Cuando esté, este comando hará GET /api/v1/projects/{project_id}/checklist "
        f"y guardará en {output_path}."
    )
