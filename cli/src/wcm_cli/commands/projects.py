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


@app.command("rollback")
def rollback_project(
    project_id: Annotated[int, typer.Argument()],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Confirma sin prompt interactivo. Requerido para CI/scripts.",
        ),
    ] = False,
) -> None:
    """v0.19.0 — deshace el deploy borrando las páginas WP creadas.

    Destructivo: requiere `--yes` o confirmación interactiva. Solo
    permitido si status ∈ {qa_failed, completed, blocked_human_input}.
    Marca el proyecto como ROLLED_BACK.
    """
    if not yes:
        confirm = typer.confirm(
            f"Esto borrará las páginas WP del proyecto {project_id}. ¿Continuar?",
            default=False,
        )
        if not confirm:
            output.info("Rollback cancelado por el usuario.")
            raise typer.Exit(code=0)

    client = ApiClient()
    result = client.post(
        f"/api/v1/projects/{project_id}/rollback",
        json={"confirm": True},
    )
    task_id = (
        result.get("task_id", "") if isinstance(result, dict) else ""
    )
    output.success(
        f"Rollback encolado para proyecto {project_id} · task {task_id[:8]}…"
    )
    output.info(
        "Sigue el progreso con: [accent]wcm projects watch "
        f"{project_id}[/]"
    )


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


# ---------- v0.17.0: status de features condicionales ----------


def _get_phase(client: ApiClient, project_id: int, phase_name: str) -> dict | None:
    """Helper: descarga las fases del proyecto y devuelve la indicada o None."""
    phases = client.get(f"/api/v1/projects/{project_id}/phases")
    if not isinstance(phases, list):
        return None
    for p in phases:
        if p.get("phase_name") == phase_name:
            return p
    return None


@app.command("woo-status")
def woo_status(project_id: Annotated[int, typer.Argument()]) -> None:
    """Resumen ejecución del agente woo-migrator del proyecto."""
    client = ApiClient()
    phase = _get_phase(client, project_id, "migrate_woo")
    if phase is None:
        output.info("Fase migrate_woo aún no ejecutada.")
        return
    summary = phase.get("output_summary") or {}
    if output.is_json_mode():
        output.emit_json(phase)
        return
    output.header(f"WooCommerce — proyecto {project_id}")
    output.key_value({
        "status": phase.get("status"),
        "iniciado": phase.get("started_at") or "—",
        "completado": phase.get("completed_at") or "—",
        "WooCommerce detectado": _fmt_bool(summary.get("woocommerce_available")),
        "productos migrados": summary.get("products_migrated", "—"),
        "productos fallidos": summary.get("products_failed", "—"),
    })


@app.command("forms-status")
def forms_status(project_id: Annotated[int, typer.Argument()]) -> None:
    """Resumen ejecución del agente forms-rebuilder del proyecto."""
    client = ApiClient()
    phase = _get_phase(client, project_id, "rebuild_forms")
    if phase is None:
        output.info("Fase rebuild_forms aún no ejecutada.")
        return
    summary = phase.get("output_summary") or {}
    if output.is_json_mode():
        output.emit_json(phase)
        return
    output.header(f"Gravity Forms — proyecto {project_id}")
    output.key_value({
        "status": phase.get("status"),
        "iniciado": phase.get("started_at") or "—",
        "completado": phase.get("completed_at") or "—",
        "Gravity Forms detectado": _fmt_bool(summary.get("gravity_forms_available")),
        "forms detectados origen": summary.get("forms_detected", "—"),
        "forms creados destino": summary.get("forms_created", "—"),
    })


@app.command("preflight")
def preflight(project_id: Annotated[int, typer.Argument()]) -> None:
    """Ejecuta los 4 chequeos pre-Start y muestra el resultado (v0.18.0).

    Devuelve exit code 1 si can_start=False (útil para CI / scripts).
    """
    client = ApiClient()
    result = client.post(f"/api/v1/projects/{project_id}/preflight")
    if not isinstance(result, dict):
        output.error(f"Respuesta inesperada del API: {type(result).__name__}")
        raise typer.Exit(code=1)

    if output.is_json_mode():
        output.emit_json(result)
    else:
        output.header(f"Preflight — proyecto {project_id}")
        _print_check("WP destino", result.get("wp_target", {}))
        _print_check("Origen", result.get("source", {}))
        _print_check("Credenciales del back", result.get("source_credentials", {}))
        plugins = result.get("plugins") or {}
        plugins_summary = ", ".join(
            f"{name}={'✓' if ok else '✗'}" for name, ok in plugins.items()
        ) or "—"
        output.info(f"Plugins destino: {plugins_summary}")
        blocking = result.get("blocking_issues") or []
        warnings = result.get("warnings") or []
        if blocking:
            output.warning(f"Bloqueantes ({len(blocking)}):")
            for m in blocking:
                output.warning(f"  ✗ {m}")
        if warnings:
            output.info(f"Avisos ({len(warnings)}):")
            for m in warnings:
                output.info(f"  ⚠ {m}")
        if result.get("can_start"):
            output.success("can_start=True · puedes arrancar el pipeline.")
        else:
            output.error("can_start=False · resuelve los bloqueantes antes del Start.")

    if not result.get("can_start"):
        raise typer.Exit(code=1)


@app.command("watch")
def watch(
    project_id: Annotated[int, typer.Argument()],
    interval_s: Annotated[
        float,
        typer.Option("--interval", help="Frecuencia de polling en segundos."),
    ] = 2.0,
) -> None:
    """Stream del estado del pipeline con stepper Rich (v0.18.0).

    Polling cada `interval_s` segundos hasta que `project.status` pasa a
    terminal (completed/failed/cancelled/qa_failed). Ctrl+C cancela
    limpio.
    """
    import time

    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    client = ApiClient()
    console = output._console()  # type: ignore[attr-defined]

    def _render() -> Panel:
        try:
            project = client.get(f"/api/v1/projects/{project_id}")
            phases = client.get(f"/api/v1/projects/{project_id}/phases") or []
        except Exception as e:  # noqa: BLE001
            return Panel(
                Text(f"Error: {type(e).__name__}: {e}", style="wcm.error"),
                title=f"Proyecto {project_id}",
            )

        status = project.get("status", "?")
        rows = []
        for ph in phases:
            icon = _phase_icon(ph.get("status"))
            name = ph.get("phase_name", "?")
            duration = _phase_duration(ph)
            rows.append(f" {icon}  {name:<22}{duration}")
        body = Text("\n".join(rows) if rows else "(sin fases registradas)", overflow="fold")
        title = f"Proyecto {project_id} · status={status}"
        return Panel(body, title=title, border_style="wcm.accent")

    try:
        with Live(_render(), console=console, refresh_per_second=2) as live:
            while True:
                project = client.get(f"/api/v1/projects/{project_id}")
                if project.get("status") in (
                    "completed",
                    "failed",
                    "cancelled",
                    "qa_failed",
                ):
                    live.update(_render())
                    break
                live.update(_render())
                time.sleep(interval_s)
        output.success(f"Pipeline terminó con status={project.get('status')}")
    except KeyboardInterrupt:
        output.info("Watch cancelado por el usuario.")


@app.command("set-source-credentials")
def set_source_credentials(
    project_id: Annotated[int, typer.Argument()],
    builder: Annotated[
        str,
        typer.Option("--builder", help="Builder origen: wix | webflow"),
    ],
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help="Wix: api_key (sensible — no aparece en stdout).",
        ),
    ] = None,
    api_token: Annotated[
        str | None,
        typer.Option(
            "--api-token",
            help="Webflow: api_token (sensible — no aparece en stdout).",
        ),
    ] = None,
    site_id: Annotated[
        str,
        typer.Option("--site-id", help="ID del site en el builder origen."),
    ] = "",
) -> None:
    """Guarda credenciales del back del origen para el proyecto (v0.18.0).

    Admin-only en el API. Se cifran con Fernet antes de persistirse.
    El comando NUNCA imprime las credenciales en stdout.
    """
    builder_norm = builder.lower()
    if builder_norm not in {"wix", "webflow"}:
        output.error("--builder debe ser 'wix' o 'webflow'.")
        raise typer.Exit(code=2)
    if not site_id:
        output.error("--site-id es obligatorio.")
        raise typer.Exit(code=2)

    payload: dict[str, str] = {"builder": builder_norm, "site_id": site_id}
    if builder_norm == "wix":
        if not api_key:
            output.error("--api-key es obligatorio para builder=wix.")
            raise typer.Exit(code=2)
        payload["api_key"] = api_key
    else:
        if not api_token:
            output.error("--api-token es obligatorio para builder=webflow.")
            raise typer.Exit(code=2)
        payload["api_token"] = api_token

    client = ApiClient()
    client.put(f"/api/v1/projects/{project_id}/source-credentials", json=payload)
    output.success(
        f"Credenciales {builder_norm} guardadas para proyecto {project_id} "
        "(cifradas con Fernet)."
    )


def _print_check(label: str, check: dict) -> None:
    """Imprime un check del preflight con icono según estado."""
    ok = bool(check.get("ok"))
    blocking = bool(check.get("blocking"))
    message = check.get("message", "")
    if ok:
        output.success(f"✓ {label}: {message}")
    elif blocking:
        output.error(f"✗ {label}: {message}")
    else:
        output.warning(f"⚠ {label}: {message}")


def _phase_icon(status: str | None) -> str:
    return {
        "completed": "✓",
        "running": "●",
        "failed": "✗",
        "skipped": "↷",
        "pending": "○",
    }.get(status or "", "○")


def _phase_duration(phase: dict) -> str:
    """Devuelve duración formateada o vacío."""
    from datetime import datetime

    started = phase.get("started_at")
    completed = phase.get("completed_at")
    if not started:
        return ""
    try:
        t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if completed:
            t1 = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        else:
            from datetime import UTC

            t1 = datetime.now(UTC)
        sec = max(0, int((t1 - t0).total_seconds()))
        if sec < 60:
            return f" · {sec}s"
        return f" · {sec // 60}m {sec % 60}s"
    except (ValueError, AttributeError):
        return ""


@app.command("wpml-status")
def wpml_status(project_id: Annotated[int, typer.Argument()]) -> None:
    """Resumen ejecución del agente wpml-configurator del proyecto."""
    client = ApiClient()
    phase = _get_phase(client, project_id, "configure_wpml")
    if phase is None:
        output.info("Fase configure_wpml aún no ejecutada.")
        return
    summary = phase.get("output_summary") or {}
    if output.is_json_mode():
        output.emit_json(phase)
        return
    output.header(f"WPML — proyecto {project_id}")
    pages_per_lang = summary.get("pages_per_lang") or {}
    output.key_value({
        "status": phase.get("status"),
        "iniciado": phase.get("started_at") or "—",
        "completado": phase.get("completed_at") or "—",
        "idiomas": ", ".join(summary.get("langs") or []) or "—",
        "idioma principal": summary.get("primary_lang") or "—",
        "páginas total": summary.get("pages_total", "—"),
        "páginas por idioma": ", ".join(f"{k}={v}" for k, v in pages_per_lang.items()) or "—",
    })
    output.info(
        "Webcafeína NO tiene licencia WPML. La configuración es manual — "
        "consulta el checklist del proyecto para los pasos."
    )
