"""Tests de los comandos v0.18.0 del módulo `projects`:

- `wcm projects preflight ID` (visualiza checks + exit code 1 si no can_start)
- `wcm projects set-source-credentials ID --builder X ...`

`watch` se valida con un smoke test mínimo de invocación (Rich Live
es difícil de testear sin TTY real; la lógica del polling se prueba
manualmente).
"""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _preflight_result(*, can_start: bool = True, blocking_issues: list[str] | None = None) -> dict:
    return {
        "wp_target": {"ok": True, "blocking": True, "message": "WP OK"},
        "plugins": {"bricks": True, "gravity_forms": True, "woocommerce": False},
        "source": {"ok": True, "blocking": True, "message": "Origen OK"},
        "source_credentials": {
            "ok": True,
            "blocking": False,
            "message": "Sin credenciales (modo público).",
        },
        "can_start": can_start,
        "blocking_issues": blocking_issues or [],
        "warnings": ["Plugin woocommerce no detectado en destino"],
        "executed_at": "2026-05-19T12:00:00Z",
    }


def test_preflight_happy_path_exit_0(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/7/preflight").return_value = httpx.Response(
            200, json=_preflight_result(can_start=True)
        )
        result = runner.invoke(app, ["projects", "preflight", "7"])
    assert result.exit_code == 0, result.output
    assert "can_start=True" in result.output
    assert "WP destino" in result.output


def test_preflight_bloqueante_exit_1(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/7/preflight").return_value = httpx.Response(
            200,
            json=_preflight_result(
                can_start=False,
                blocking_issues=["WP destino: REST 502"],
            ),
        )
        result = runner.invoke(app, ["projects", "preflight", "7"])
    assert result.exit_code == 1, result.output
    assert "REST 502" in result.output


def test_set_source_credentials_wix_ok(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.put("/api/v1/projects/7/source-credentials").return_value = httpx.Response(
            200, json={"id": 7, "client_name": "x"}
        )
        result = runner.invoke(
            app,
            [
                "projects",
                "set-source-credentials",
                "7",
                "--builder",
                "wix",
                "--api-key",
                "secret-key-xxxxxxxxxxxxxxxxxx",
                "--site-id",
                "site-1234abcd",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "wix" in result.output.lower()
    # La api_key NUNCA debe aparecer en stdout (privacidad).
    assert "secret-key-xxxxxxxxxxxxxxxxxx" not in result.output


def test_set_source_credentials_webflow_ok(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.put("/api/v1/projects/7/source-credentials").return_value = httpx.Response(
            200, json={"id": 7, "client_name": "x"}
        )
        result = runner.invoke(
            app,
            [
                "projects",
                "set-source-credentials",
                "7",
                "--builder",
                "webflow",
                "--api-token",
                "tok-yyyyyyyyyyyyyyyyyyyyyy",
                "--site-id",
                "site-2345defg",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "webflow" in result.output.lower()
    assert "tok-yyyyyyyyyyyyyyyyyyyyyy" not in result.output


def test_set_source_credentials_builder_invalido(
    runner: CliRunner, authenticated
) -> None:
    result = runner.invoke(
        app,
        [
            "projects",
            "set-source-credentials",
            "7",
            "--builder",
            "squarespace",
            "--site-id",
            "site-1",
        ],
    )
    assert result.exit_code == 2
    assert "wix" in result.output.lower() or "webflow" in result.output.lower()


def test_set_source_credentials_wix_sin_api_key_falla(
    runner: CliRunner, authenticated
) -> None:
    """builder=wix requiere --api-key, sin él exit 2."""
    result = runner.invoke(
        app,
        [
            "projects",
            "set-source-credentials",
            "7",
            "--builder",
            "wix",
            "--site-id",
            "site-1",
        ],
    )
    assert result.exit_code == 2
    assert "api-key" in result.output.lower()


def test_set_source_credentials_sin_site_id_falla(
    runner: CliRunner, authenticated
) -> None:
    result = runner.invoke(
        app,
        [
            "projects",
            "set-source-credentials",
            "7",
            "--builder",
            "wix",
            "--api-key",
            "x" * 30,
        ],
    )
    assert result.exit_code == 2
    assert "site-id" in result.output.lower()
