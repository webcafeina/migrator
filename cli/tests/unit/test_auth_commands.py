"""Tests de los comandos auth (login/logout/me)."""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli import config as cli_config
from wcm_cli.main import app


def test_login_success_saves_token(runner: CliRunner) -> None:
    with respx.mock(base_url="http://api.test") as router:
        # API responde 200 con cookie wcm_session
        route = router.post("/api/v1/auth/login")
        route.return_value = httpx.Response(
            200,
            json={
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "test@webcafeina.com",
                "name": "Test",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-05-13T10:00:00Z",
                "updated_at": "2026-05-13T10:00:00Z",
            },
            headers={
                "set-cookie": "wcm_session=fake-jwt-token; Path=/; HttpOnly"
            },
        )

        result = runner.invoke(
            app, ["login"], input="test@webcafeina.com\nsupersecret\n"
        )

    assert result.exit_code == 0, result.output
    assert "Sesión iniciada" in result.output
    # Token guardado
    from wcm_cli.config import load_token
    assert load_token() == "fake-jwt-token"


def test_login_wrong_credentials_shows_error(runner: CliRunner) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/auth/login").return_value = httpx.Response(
            401, json={"error": {"code": "unauthorized", "message": "bad"}}
        )
        result = runner.invoke(app, ["login"], input="x@y.com\npass\n")

    assert result.exit_code != 0
    assert "inválidas" in result.output or "Credenciales" in result.output


def test_logout_clears_token(runner: CliRunner, authenticated) -> None:
    # WCM_TOKEN env tiene preferencia; logout solo borra el fichero local.
    # Aún así escribimos uno para asegurarnos que se borra.
    cli_config.CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cli_config.CREDENTIALS_PATH.write_text('{"token":"x"}', encoding="utf-8")

    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "Sesión cerrada" in result.output
    assert not cli_config.CREDENTIALS_PATH.exists()


def test_me_command_returns_user(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/auth/me").return_value = httpx.Response(
            200,
            json={
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "test@webcafeina.com",
                "name": "Test",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-05-13T10:00:00Z",
                "updated_at": "2026-05-13T10:00:00Z",
            },
        )
        result = runner.invoke(app, ["auth", "me"])

    assert result.exit_code == 0
    assert "test@webcafeina.com" in result.output


def test_me_without_auth_returns_error(runner: CliRunner) -> None:
    # Sin WCM_TOKEN ni fichero → CliAuthError
    result = runner.invoke(app, ["auth", "me"])
    assert result.exit_code != 0
    assert "iniciado sesión" in result.output or "login" in result.output
