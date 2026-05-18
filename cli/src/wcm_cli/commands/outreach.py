"""Comandos sobre secuencias de contacto comercial (outreach).

Cubre el ciclo completo del flujo §8 paso 6 desde terminal:
- `wcm outreach list` — lista de secuencias.
- `wcm outreach show ID` — detalle con steps + sends.
- `wcm outreach approve ID` — DRAFT_PENDING_REVIEW/PAUSED → READY.
- `wcm outreach pause ID` — READY/IN_PROGRESS → PAUSED.
- `wcm outreach cancel ID` — cualquier estado activo → CANCELLED.
- `wcm outreach send ID` — encola envío real (Resend si está
  configurado; fallback "skipped" si no).

NO incluye edición de pasos por CLI (se hace desde el dashboard con
el editor inline — el caso "rectificar typo del LLM" es típicamente
visual, no scriptable).
"""

from __future__ import annotations

from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient
from wcm_cli.errors import CliInputError

app = typer.Typer(help="Gestión de secuencias de contacto comercial")


# ----- castellano de status (espejo del helper del dashboard) -----

_SEQ_STATUS_ES: dict[str, str] = {
    "draft_pending_review": "Borrador pendiente",
    "ready": "Lista para enviar",
    "in_progress": "Enviando",
    "completed": "Completada",
    "paused": "Pausada",
    "cancelled": "Cancelada",
    "opted_out": "Baja (RGPD)",
}

_SEND_STATUS_ES: dict[str, str] = {
    "queued": "En cola",
    "sent": "Enviado",
    "bounced": "Rebotado",
    "opened": "Abierto",
    "replied": "Respondido",
    "failed": "Falló",
}


def _seq_status(s: str) -> str:
    return _SEQ_STATUS_ES.get(s.lower(), s)


def _send_status(s: str) -> str:
    return _SEND_STATUS_ES.get(s.lower(), s)


@app.command("list")
def list_sequences(
    lead_id: Annotated[
        int | None, typer.Option("--lead-id", help="Filtrar por lead")
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            help="Filtrar por status (draft_pending_review|ready|paused|...)"
        ),
    ] = None,
    limit: Annotated[int, typer.Option(help="Máximo de resultados")] = 50,
) -> None:
    """Lista secuencias de contacto con filtros opcionales."""
    params: dict[str, object] = {"limit": limit}
    if lead_id is not None:
        params["lead_id"] = lead_id
    if status:
        params["status"] = status

    client = ApiClient()
    seqs = client.get("/api/v1/outreach/sequences", params=params)

    if not seqs:
        output.info("Sin secuencias que coincidan con los filtros.")
        return

    output.render_table(
        f"Secuencias ({len(seqs)})",
        ["id", "lead_id", "name", "template", "status", "legal_ok", "creada"],
        [
            [
                s["id"],
                s["lead_id"],
                s["name"][:50],
                s["template_name"],
                _seq_status(s["status"]),
                "✓" if s["legal_validation_passed"] else "✗",
                s["created_at"][:10],
            ]
            for s in seqs
        ],
        json_payload=seqs,
    )


@app.command("show")
def show_sequence(
    sequence_id: Annotated[int, typer.Argument(help="ID de la secuencia")],
) -> None:
    """Detalle de una secuencia: pasos + envíos realizados."""
    client = ApiClient()
    seq = client.get(f"/api/v1/outreach/sequences/{sequence_id}")

    if output.is_json_mode():
        output.emit_json(seq)
        return

    output.header(f"Secuencia #{seq['id']} — {seq['name']}")
    output.key_value({
        "lead_id": seq["lead_id"],
        "plantilla": seq["template_name"],
        "canal": seq.get("channel") or "—",
        "status": _seq_status(seq["status"]),
        "validación legal": "OK" if seq["legal_validation_passed"] else "FALLA",
        "creada": seq["created_at"],
        "actualizada": seq["updated_at"],
    })

    output.header("Pasos")
    for idx, step in enumerate(seq.get("steps_json") or []):
        delay = step.get("delay_days_from_previous", step.get("delay_days", 0))
        delay_label = "día 0" if delay == 0 else f"+{delay}d desde anterior"
        output.info(
            f"  [Paso {idx + 1}] {delay_label}\n"
            f"  Asunto: {step.get('subject') or '(vacío)'}\n"
            f"  Cuerpo ({len(step.get('body', ''))} chars)\n"
        )

    sends = seq.get("sends") or []
    if sends:
        output.header(f"Envíos ({len(sends)})")
        output.render_table(
            "",
            ["step", "status", "sent_at", "opened_at", "replied_at", "bounced_at"],
            [
                [
                    s["step_index"] + 1,
                    _send_status(s["status"]),
                    (s.get("sent_at") or "—")[:19],
                    (s.get("opened_at") or "—")[:19],
                    (s.get("replied_at") or "—")[:19],
                    (s.get("bounced_at") or "—")[:19],
                ]
                for s in sends
            ],
        )
    else:
        output.info(
            "Sin envíos aún (status anterior a READY o aún no encolados)."
        )


def _transition(sequence_id: int, action: str, verb_es: str) -> None:
    """Helper compartido para approve/pause/cancel."""
    client = ApiClient()
    seq = client.post(
        f"/api/v1/outreach/sequences/{sequence_id}/transition",
        json={"action": action},
    )
    output.success(
        f"Secuencia #{seq['id']} {verb_es} · status={_seq_status(seq['status'])}"
    )


@app.command("approve")
def approve_sequence(
    sequence_id: Annotated[int, typer.Argument()],
) -> None:
    """Aprueba la secuencia (DRAFT_PENDING_REVIEW/PAUSED → READY).

    Requiere validación legal pasada. Si no, el API devuelve 409 con
    el motivo concreto. Usar `wcm outreach show ID` para ver el
    estado de validación.
    """
    _transition(sequence_id, "approve", "aprobada")


@app.command("pause")
def pause_sequence(
    sequence_id: Annotated[int, typer.Argument()],
) -> None:
    """Pausa la secuencia (READY/IN_PROGRESS → PAUSED). Reversible
    con `wcm outreach approve ID`."""
    _transition(sequence_id, "pause", "pausada")


@app.command("cancel")
def cancel_sequence(
    sequence_id: Annotated[int, typer.Argument()],
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help="Confirma cancelación (irreversible)"),
    ] = False,
) -> None:
    """Cancela la secuencia (cualquier estado activo → COMPLETED).
    Operación irreversible — para reintentar hay que componer un draft
    nuevo. Requiere `--confirm`."""
    if not confirm:
        raise CliInputError(
            "Cancelar requiere --confirm (irreversible).",
            hint=(
                "Si solo quieres parar el envío y poder reanudar,\n"
                "usa `wcm outreach pause ID`."
            ),
        )
    _transition(sequence_id, "cancel", "cancelada")


@app.command("send")
def send_sequence(
    sequence_id: Annotated[int, typer.Argument()],
    step_index: Annotated[
        int | None,
        typer.Option(
            "--step",
            help="Index del paso concreto a enviar (default: siguiente QUEUED)",
        ),
    ] = None,
) -> None:
    """Encola el envío real del siguiente paso QUEUED de la secuencia.

    Requiere status READY o IN_PROGRESS. El worker procesa el job:
    - Con `RESEND_API_KEY` configurado → envía vía Resend.
    - Sin Resend → el agent devuelve summary 'skipped' (no envía nada
      pero el sequence avanza). Útil para tests y export manual.

    Tras encolar, usar `wcm outreach show ID` para ver el estado.
    """
    client = ApiClient()
    params = {"step_index": step_index} if step_index is not None else None
    resp = client.post(
        f"/api/v1/outreach/sequences/{sequence_id}/send", params=params
    )
    task_short = (resp.get("task_id") or "")[:8]
    output.success(
        f"Envío encolado · sequence #{sequence_id} · step "
        f"{resp.get('step_index', '?')} · task {task_short}…"
    )


# ===== v0.14.0: templates preview + test-send =====


@app.command("preview")
def preview_step(
    sequence_id: Annotated[int, typer.Argument(help="ID de la secuencia")],
    step_index: Annotated[int, typer.Argument(help="Index del paso (0, 1, …)")],
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Abrir el HTML renderizado en el navegador (tempfile)",
        ),
    ] = False,
) -> None:
    """Renderiza el HTML preview de un step y lo imprime (o abre en
    navegador con `--open`).
    """
    client = ApiClient()
    resp = client.get(
        f"/api/v1/outreach/sequences/{sequence_id}/steps/{step_index}/preview"
    )
    html = str(resp.get("html", ""))
    subject = resp.get("subject") or ""

    if open_browser:
        import tempfile
        import webbrowser

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(html)
            path = f.name
        webbrowser.open(f"file://{path}")
        output.success(f"HTML abierto en navegador (tempfile: {path})")
    else:
        if subject:
            output.info(f"Asunto: {subject}")
        typer.echo(html)


@app.command("test-send")
def test_send_step(
    sequence_id: Annotated[int, typer.Argument(help="ID de la secuencia")],
    step_index: Annotated[int, typer.Argument(help="Index del paso (0, 1, …)")],
    to: Annotated[
        str,
        typer.Option("--to", help="Email destino del envío de prueba", prompt=True),
    ],
) -> None:
    """Envía el step a `--to` vía Resend para previsualizarlo en una
    bandeja real. NO crea OutreachSend ni muta el sequence (queda en
    AuditLog como TEST_SEND).
    """
    if "@" not in to or "." not in to.split("@", 1)[-1]:
        raise CliInputError(f"Email no válido: {to!r}")

    client = ApiClient()
    resp = client.post(
        f"/api/v1/outreach/sequences/{sequence_id}/steps/{step_index}/test-send",
        json={"to": to},
    )
    msg_id = resp.get("provider_message_id") or "—"
    output.success(
        f"Correo de prueba enviado a {to} · provider_message_id={msg_id}"
    )


# ===== v0.14.0: templates preview =====


templates_app = typer.Typer(help="Gestión de plantillas Jinja2")


@templates_app.command("preview")
def preview_template_cmd(
    template_id: Annotated[int, typer.Argument(help="ID de la plantilla")],
    open_browser: Annotated[
        bool, typer.Option("--open/--no-open", help="Abrir en navegador")
    ] = False,
) -> None:
    """Renderiza la plantilla con un lead demo y devuelve el HTML."""
    client = ApiClient()
    resp = client.get(f"/api/v1/templates/{template_id}/preview")
    html = str(resp.get("html", ""))
    subject = resp.get("subject") or ""

    if open_browser:
        import tempfile
        import webbrowser

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        webbrowser.open(f"file://{path}")
        output.success(f"HTML abierto en navegador (tempfile: {path})")
    else:
        if subject:
            output.info(f"Asunto: {subject}")
        typer.echo(html)


app.add_typer(templates_app, name="templates")
