"""Tests de los comandos status de features v0.17.0:

- `wcm projects woo-status ID`
- `wcm projects forms-status ID`
- `wcm projects wpml-status ID`
"""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _phase(
    phase_name: str,
    *,
    status: str = "completed",
    output_summary: dict | None = None,
) -> dict:
    return {
        "id": 1,
        "project_id": 7,
        "phase_name": phase_name,
        "status": status,
        "started_at": "2026-05-19T10:00:00Z",
        "completed_at": "2026-05-19T10:05:00Z",
        "attempt": 1,
        "error_log": None,
        "output_summary": output_summary,
        "created_at": "2026-05-19T10:00:00Z",
        "updated_at": "2026-05-19T10:05:00Z",
    }


def test_woo_status_sin_fase(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=[]
        )
        result = runner.invoke(app, ["projects", "woo-status", "7"])
    assert result.exit_code == 0, result.output
    assert "aún no ejecutada" in result.output


def test_woo_status_con_summary(runner: CliRunner, authenticated) -> None:
    phases = [
        _phase("scrape_origin", status="completed"),
        _phase(
            "migrate_woo",
            output_summary={
                "woocommerce_available": True,
                "products_migrated": 12,
                "products_failed": 1,
            },
        ),
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=phases
        )
        result = runner.invoke(app, ["projects", "woo-status", "7"])
    assert result.exit_code == 0, result.output
    assert "12" in result.output
    assert "WooCommerce" in result.output


def test_forms_status_con_summary(runner: CliRunner, authenticated) -> None:
    phases = [
        _phase(
            "rebuild_forms",
            output_summary={
                "gravity_forms_available": False,
                "forms_detected": 3,
                "forms_created": 0,
            },
        ),
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=phases
        )
        result = runner.invoke(app, ["projects", "forms-status", "7"])
    assert result.exit_code == 0, result.output
    assert "Gravity Forms" in result.output
    assert "3" in result.output


def test_wpml_status_con_summary(runner: CliRunner, authenticated) -> None:
    phases = [
        _phase(
            "configure_wpml",
            output_summary={
                "langs": ["es", "en", "fr"],
                "primary_lang": "es",
                "pages_total": 30,
                "pages_per_lang": {"es": 12, "en": 10, "fr": 8},
            },
        ),
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=phases
        )
        result = runner.invoke(app, ["projects", "wpml-status", "7"])
    assert result.exit_code == 0, result.output
    assert "es, en, fr" in result.output
    assert "30" in result.output
    assert "NO tiene licencia" in result.output


def test_wpml_status_sin_fase(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=[]
        )
        result = runner.invoke(app, ["projects", "wpml-status", "7"])
    assert result.exit_code == 0, result.output
    assert "aún no" in result.output


def test_woo_status_json_mode(runner: CliRunner, authenticated, monkeypatch) -> None:
    monkeypatch.setenv("WCM_JSON", "1")
    phases = [
        _phase("migrate_woo", output_summary={"products_migrated": 5}),
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/phases").return_value = httpx.Response(
            200, json=phases
        )
        result = runner.invoke(app, ["projects", "woo-status", "7"])
    assert result.exit_code == 0, result.output
    # JSON mode emite el dict completo del phase.
    assert "migrate_woo" in result.output
    assert "products_migrated" in result.output
