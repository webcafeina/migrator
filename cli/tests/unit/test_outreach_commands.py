"""Tests del CLI `wcm outreach` (v0.12.1).

Cubre el flujo §8 paso 6 desde terminal: list, show, approve, pause,
cancel, send.
"""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _seq(seq_id: int = 1, **over: object) -> dict:
    base = {
        "id": seq_id,
        "lead_id": 5,
        "template_name": "wix_intro_es",
        "name": "Outreach inicial · Test",
        "channel": "email",
        "steps_json": [
            {
                "step_index": 0,
                "subject": "Asunto 1",
                "body": "Cuerpo del paso 1...",
                "delay_days_from_previous": 0,
            },
        ],
        "status": "draft_pending_review",
        "legal_validation_passed": True,
        "legal_validator_version": "v1.0",
        "created_at": "2026-05-14T11:00:00Z",
        "updated_at": "2026-05-14T11:00:00Z",
    }
    base.update(over)
    return base


# ---------- list ----------


def test_list_sin_filtros(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/outreach/sequences").return_value = httpx.Response(
            200, json=[_seq(1), _seq(2, name="Otra")],
        )
        result = runner.invoke(app, ["outreach", "list"])
    assert result.exit_code == 0, result.output
    assert "Secuencias (2)" in result.output


def test_list_sin_resultados(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/outreach/sequences").return_value = httpx.Response(
            200, json=[]
        )
        result = runner.invoke(app, ["outreach", "list"])
    assert result.exit_code == 0
    assert "Sin secuencias" in result.output


def test_list_traduce_status_castellano(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/outreach/sequences").return_value = httpx.Response(
            200,
            json=[_seq(1, status="draft_pending_review"), _seq(2, status="ready")],
        )
        result = runner.invoke(app, ["outreach", "list"])
    # Rich envuelve la celda en varias líneas; verificamos las palabras
    # clave por separado.
    assert "Borrador" in result.output and "pendiente" in result.output
    assert "Lista para" in result.output or "para enviar" in result.output


# ---------- show ----------


def test_show_pinta_pasos_y_sends(runner: CliRunner, authenticated) -> None:
    seq = _seq(1, status="ready")
    seq["sends"] = [
        {
            "step_index": 0,
            "status": "sent",
            "sent_at": "2026-05-18T10:00:00Z",
            "opened_at": None,
            "replied_at": None,
            "bounced_at": None,
        },
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/outreach/sequences/1").return_value = httpx.Response(
            200, json=seq
        )
        result = runner.invoke(app, ["outreach", "show", "1"])
    assert result.exit_code == 0, result.output
    assert "Paso 1" in result.output
    assert "Asunto 1" in result.output
    assert "Envíos (1)" in result.output
    assert "Enviado" in result.output  # status castellano


def test_show_sin_sends_explica(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/outreach/sequences/1").return_value = httpx.Response(
            200, json=_seq(1)
        )
        result = runner.invoke(app, ["outreach", "show", "1"])
    assert "Sin envíos aún" in result.output


# ---------- approve / pause / cancel ----------


def test_approve_ok(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post(
            "/api/v1/outreach/sequences/1/transition"
        ).return_value = httpx.Response(200, json=_seq(1, status="ready"))
        result = runner.invoke(app, ["outreach", "approve", "1"])
    assert result.exit_code == 0, result.output
    assert "aprobada" in result.output.lower()
    assert "Lista para enviar" in result.output


def test_approve_409_se_propaga(runner: CliRunner, authenticated) -> None:
    """Si el backend rechaza (legal_validation_passed=false), el CLI
    debe propagar el error con exit code != 0."""
    with respx.mock(base_url="http://api.test") as router:
        router.post(
            "/api/v1/outreach/sequences/1/transition"
        ).return_value = httpx.Response(
            409,
            json={
                "error": {
                    "code": "conflict",
                    "message": "No se puede aprobar — validación legal falla",
                }
            },
        )
        result = runner.invoke(app, ["outreach", "approve", "1"])
    assert result.exit_code != 0
    assert "validación legal" in result.output.lower()


def test_pause_ok(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post(
            "/api/v1/outreach/sequences/1/transition"
        ).return_value = httpx.Response(200, json=_seq(1, status="paused"))
        result = runner.invoke(app, ["outreach", "pause", "1"])
    assert result.exit_code == 0
    assert "pausada" in result.output.lower()


def test_cancel_requires_confirm(runner: CliRunner, authenticated) -> None:
    result = runner.invoke(app, ["outreach", "cancel", "1"])
    assert result.exit_code != 0
    assert "--confirm" in result.output


def test_cancel_with_confirm(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post(
            "/api/v1/outreach/sequences/1/transition"
        ).return_value = httpx.Response(
            200, json=_seq(1, status="completed")
        )
        result = runner.invoke(
            app, ["outreach", "cancel", "1", "--confirm"]
        )
    assert result.exit_code == 0
    assert "cancelada" in result.output.lower()


# ---------- send ----------


def test_send_ok(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post(
            "/api/v1/outreach/sequences/1/send"
        ).return_value = httpx.Response(
            202,
            json={
                "task_id": "abc12345-def0-1111-aaaa-bbbbccccdddd",
                "status": "queued",
                "send_id": 1,
                "step_index": 0,
            },
        )
        result = runner.invoke(app, ["outreach", "send", "1"])
    assert result.exit_code == 0, result.output
    assert "Envío encolado" in result.output
    assert "abc12345" in result.output


def test_send_with_step_index(runner: CliRunner, authenticated) -> None:
    """Verifica que --step se propaga como query param `step_index`."""
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            202,
            json={"task_id": "t", "status": "queued", "send_id": 1, "step_index": 2},
        )

    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/outreach/sequences/1/send").mock(
            side_effect=_capture
        )
        result = runner.invoke(
            app, ["outreach", "send", "1", "--step", "2"]
        )
    assert result.exit_code == 0
    assert captured["params"].get("step_index") == "2"
