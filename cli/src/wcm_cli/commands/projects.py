"""Comandos sobre proyectos de migración."""

from __future__ import annotations

from pathlib import Path
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
    output_path: Annotated[
        str | None,
        typer.Option(
            "--out", "-o", help="Ruta destino. Si se omite, escribe en cwd."
        ),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option(
            "--format", "-f", help="Formato de salida: pdf | md", case_sensitive=False
        ),
    ] = "pdf",
) -> None:
    """Descarga el checklist humano del proyecto generado por checklist-generator.

    El backend devuelve 302 → R2 (https) o stream local (file://). La CLI
    sigue redirects y vuelca bytes al fichero destino.
    """
    fmt_norm = fmt.lower()
    if fmt_norm not in {"pdf", "md"}:
        output.error("--format debe ser 'pdf' o 'md'.")
        raise typer.Exit(code=2)

    target = Path(output_path) if output_path else Path.cwd() / f"checklist-{project_id}.{fmt_norm}"
    client = ApiClient()
    body = client.get_bytes(
        f"/api/v1/projects/{project_id}/checklist/download",
        params={"format": fmt_norm},
    )
    target.write_bytes(body)
    output.success(f"Checklist exportado: {target} ({len(body):,} bytes)")


@app.command("diff")
def project_diff(project_id: Annotated[int, typer.Argument()]) -> None:
    """Lista las comparaciones visuales página-a-página del proyecto."""
    client = ApiClient()
    response = client.get(f"/api/v1/projects/{project_id}/visual-diffs")
    pages = response.get("pages", []) if isinstance(response, dict) else []

    if not pages:
        output.info("Sin comparaciones visuales. ¿Ya ejecutó visual-diff?")
        return

    output.render_table(
        f"Visual diff — proyecto {project_id} ({len(pages)} páginas)",
        ["página", "score", "viewport", "overlay"],
        [
            [
                p["page_path"],
                f"{int((p.get('score') or 0) * 100)}%" if p.get("score") is not None else "—",
                p.get("viewport_width") or "—",
                "sí" if p.get("overlay_url") else "no",
            ]
            for p in pages
        ],
        json_payload=response,
    )


@app.command("qa-report")
def project_qa(project_id: Annotated[int, typer.Argument()]) -> None:
    """Resumen del último reporte QA (Lighthouse + W3C + links + SEO)."""
    client = ApiClient()
    report = client.get(f"/api/v1/projects/{project_id}/qa-report")

    if not report:
        output.info("Sin reporte QA. ¿Ya ejecutó qa-runner?")
        return

    if output.is_json_mode():
        output.emit_json(report)
        return

    output.header(f"QA report — proyecto {project_id}")
    output.key_value({
        "Lighthouse perf desktop": _fmt_score(report.get("lighthouse_perf_desktop")),
        "Lighthouse perf mobile": _fmt_score(report.get("lighthouse_perf_mobile")),
        "Accesibilidad": _fmt_score(report.get("lighthouse_a11y_avg")),
        "Best practices": _fmt_score(report.get("lighthouse_best_practices_avg")),
        "SEO": _fmt_score(report.get("lighthouse_seo_avg")),
        "Errores HTML W3C": report.get("html_validator_errors_count", 0),
        "Warnings HTML W3C": report.get("html_validator_warnings_count", 0),
        "Links rotos": f"{report.get('broken_links_count', 0)} / {report.get('total_links_checked', 0)}",
        "HTTPS válido": _fmt_bool(report.get("https_valid")),
        "robots.txt": _fmt_bool(report.get("robots_accessible")),
        "sitemap.xml": _fmt_bool(report.get("sitemap_accessible")),
        "generado": report.get("created_at") or "—",
    })


def _fmt_score(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value}/100"


def _fmt_bool(value: bool | None) -> str:
    if value is None:
        return "—"
    return "OK" if value else "FAIL"
