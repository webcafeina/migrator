"""Tests del CLI `wcm users` (v0.13.0)."""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _user(
    user_id: str = "00000000-0000-0000-0000-000000000001",
    email: str = "alguien@webcafeina.com",
    role: str = "operator",
    is_active: bool = True,
) -> dict:
    return {
        "id": user_id,
        "email": email,
        "name": "Test User",
        "role": role,
        "is_active": is_active,
        "created_at": "2026-05-18T12:00:00Z",
        "updated_at": "2026-05-18T12:00:00Z",
    }


# ---------- list ----------


def test_list_users_ok(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(
            200, json=[_user(email="a@webcafeina.com"), _user(email="b@webcafeina.com")],
        )
        result = runner.invoke(app, ["users", "list"])
    assert result.exit_code == 0, result.output
    assert "Usuarios (2)" in result.output
    assert "a@webcafeina.com" in result.output


def test_list_users_vacio(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(200, json=[])
        result = runner.invoke(app, ["users", "list"])
    assert result.exit_code == 0
    assert "Sin usuarios" in result.output


# ---------- create ----------


def test_create_user_con_password_explicito(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/users").return_value = httpx.Response(
            201, json=_user(email="nuevo@x.com", role="admin")
        )
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--email", "nuevo@x.com",
                "--name", "Nuevo",
                "--role", "admin",
                "--password", "passwordsegura123",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "nuevo@x.com" in result.output
    assert "admin" in result.output


def test_create_user_genera_password_si_omitido(
    runner: CliRunner, authenticated
) -> None:
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as jsonlib
        captured["body"] = jsonlib.loads(request.content)
        return httpx.Response(201, json=_user())

    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/users").mock(side_effect=_capture)
        result = runner.invoke(
            app,
            [
                "users", "create",
                "--email", "x@y.com",
                "--name", "X",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "Password generado:" in result.output
    assert len(captured["body"]["password"]) >= 12


def test_create_user_rechaza_rol_invalido(
    runner: CliRunner, authenticated
) -> None:
    result = runner.invoke(
        app,
        [
            "users", "create",
            "--email", "x@y.com",
            "--name", "X",
            "--role", "superadmin",
        ],
    )
    assert result.exit_code != 0
    assert "Rol inválido" in result.output


# ---------- set-role ----------


def test_set_role_resuelve_email_y_patcha(
    runner: CliRunner, authenticated
) -> None:
    captured = {}

    def _patch_capture(request: httpx.Request) -> httpx.Response:
        import json as jsonlib
        captured["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json=_user(role="admin"))

    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(
            200,
            json=[
                _user(user_id="abc-123", email="match@x.com", role="operator"),
            ],
        )
        router.patch("/api/v1/users/abc-123").mock(side_effect=_patch_capture)
        result = runner.invoke(
            app,
            ["users", "set-role", "match@x.com", "--role", "admin"],
        )
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"role": "admin"}


def test_set_role_email_no_existe(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(200, json=[])
        result = runner.invoke(
            app,
            ["users", "set-role", "noexiste@x.com", "--role", "admin"],
        )
    assert result.exit_code != 0
    assert "no encontrado" in result.output.lower()


# ---------- activate / deactivate ----------


def test_deactivate_user(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(
            200, json=[_user(user_id="u1", email="x@y.com", is_active=True)],
        )
        router.patch("/api/v1/users/u1").return_value = httpx.Response(
            200, json=_user(user_id="u1", email="x@y.com", is_active=False),
        )
        result = runner.invoke(app, ["users", "deactivate", "x@y.com"])
    assert result.exit_code == 0
    assert "desactivado" in result.output.lower()


# ---------- delete ----------


def test_delete_requires_confirm(runner: CliRunner, authenticated) -> None:
    result = runner.invoke(app, ["users", "delete", "x@y.com"])
    assert result.exit_code != 0
    assert "--confirm" in result.output


def test_delete_with_confirm(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/users").return_value = httpx.Response(
            200, json=[_user(user_id="u1", email="x@y.com")],
        )
        router.delete("/api/v1/users/u1").return_value = httpx.Response(204)
        result = runner.invoke(
            app, ["users", "delete", "x@y.com", "--confirm"]
        )
    assert result.exit_code == 0
    assert "borrado permanentemente" in result.output.lower()
