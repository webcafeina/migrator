"""Tests básicos del CLI: --help, --version, subcomandos visibles."""

from __future__ import annotations

from typer.testing import CliRunner

from wcm_cli.main import app


def test_help_shows_main_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = result.output
    # Comandos top-level deben aparecer
    for cmd in ("setup", "doctor", "login", "logout", "projects", "leads", "campaigns"):
        assert cmd in output, f"Comando '{cmd}' no aparece en --help"


def test_no_args_shows_help(runner: CliRunner) -> None:
    """Sin argumentos, Typer debe mostrar el help (no_args_is_help=True)."""
    result = runner.invoke(app, [])
    # exit_code != 0 cuando muestra help vacío en Typer
    assert "Usage" in result.output or "Webcafeína" in result.output


def test_projects_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["projects", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "get", "start", "resume", "cancel", "new"):
        assert sub in result.output


def test_leads_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["leads", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "get", "refingerprint"):
        assert sub in result.output
