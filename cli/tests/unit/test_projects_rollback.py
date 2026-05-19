"""Tests del comando `wcm projects rollback ID` (v0.19.0)."""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def test_rollback_yes_encola(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/7/rollback").return_value = httpx.Response(
            202, json={"task_id": "task-rollback-abc123", "project_id": 7}
        )
        result = runner.invoke(app, ["projects", "rollback", "7", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Rollback encolado" in result.output
    assert "task task-rol" in result.output  # 8 chars del task_id, Rich puede truncar después


def test_rollback_sin_yes_cancela_si_no_confirma(
    runner: CliRunner, authenticated
) -> None:
    """Sin --yes y respondiendo 'n' al prompt, exit 0 sin tocar API."""
    with respx.mock(base_url="http://api.test"):
        result = runner.invoke(app, ["projects", "rollback", "7"], input="n\n")
    assert result.exit_code == 0
    assert "cancelado" in result.output.lower()


def test_rollback_sin_yes_confirma_y_encola(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/7/rollback").return_value = httpx.Response(
            202, json={"task_id": "task-xyz789", "project_id": 7}
        )
        result = runner.invoke(app, ["projects", "rollback", "7"], input="y\n")
    assert result.exit_code == 0
    assert "Rollback encolado" in result.output


def test_rollback_api_error_409(runner: CliRunner, authenticated) -> None:
    """Si API responde 409 (status no permitido), CLI exit != 0."""
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/7/rollback").return_value = httpx.Response(
            409,
            json={
                "error": {
                    "code": "conflict",
                    "message": "Rollback solo permitido si status ∈ ...",
                }
            },
        )
        result = runner.invoke(app, ["projects", "rollback", "7", "--yes"])
    assert result.exit_code != 0
    assert "solo permitido" in result.output
