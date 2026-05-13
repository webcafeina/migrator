"""Tests de comandos de dominio: leads, projects, campaigns."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- leads ----------

def test_leads_list_renders_table(runner: CliRunner, authenticated) -> None:
    leads_payload = [
        {
            "id": 1, "url": "https://example1.com/", "sector": "rest",
            "region": "Madrid", "country": "ES",
            "builder_detected": "wix", "builder_confidence": 0.85,
            "builder_evidence": [], "emails": [], "phones": [],
            "social_links": {}, "status": "fingerprinted", "score": 45,
            "last_crawl_at": None, "embedding_model": None, "embedding_at": None,
            "created_at": _iso_now(), "updated_at": _iso_now(),
        }
    ]
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/leads").return_value = httpx.Response(200, json=leads_payload)
        result = runner.invoke(app, ["leads", "list"])

    assert result.exit_code == 0, result.output
    # Rich puede truncar URLs largas por width → assert sobre prefijo o título
    assert "Leads" in result.output  # título de la tabla
    assert "wix" in result.output.lower()
    assert "exam" in result.output  # prefijo del URL aunque trunque


def test_leads_list_json_mode(runner: CliRunner, authenticated) -> None:
    leads_payload = []
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/leads").return_value = httpx.Response(200, json=leads_payload)
        result = runner.invoke(app, ["--json", "leads", "list"])

    # En json mode no debe haber tabla; debe haber JSON parseable
    # (puede emitir "Sin leads..." porque payload es vacío)
    assert result.exit_code == 0


def test_leads_refingerprint_enqueues(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads/42/refingerprint").return_value = httpx.Response(
            202, json={"task_id": "task-xyz", "status": "queued"}
        )
        result = runner.invoke(app, ["leads", "refingerprint", "42"])

    assert result.exit_code == 0
    assert "task-xyz" in result.output


# ---------- projects ----------

def _project_payload(pid: int = 1):
    return {
        "id": pid,
        "lead_id": None,
        "client_name": "Demo S.L.",
        "source_url": "https://demo.example/",
        "target_domain": None,
        "builder_source": None,
        "has_ecommerce": False,
        "is_multilang": False,
        "langs": [],
        "primary_lang": None,
        "asset_storage": "wp_local",
        "preserve_paths": True,
        "plan": None,
        "hosting_target_json": None,
        "theme_styles_origin": None,
        "visual_diff_avg_score": None,
        "status": "queued",
        "started_at": None,
        "completed_at": None,
        "estimated_go_live_at": None,
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
    }


def test_projects_new_creates_and_shows_id(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects").return_value = httpx.Response(
            201, json=_project_payload(pid=99)
        )
        result = runner.invoke(
            app,
            ["projects", "new", "--source", "https://demo.example/", "--client", "Demo S.L."],
        )

    assert result.exit_code == 0
    assert "99" in result.output
    assert "Demo S.L." in result.output


def test_projects_start_encola(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/projects/99/start").return_value = httpx.Response(
            202, json={"task_id": "t-1", "status": "queued", "project_id": 99}
        )
        result = runner.invoke(app, ["projects", "start", "99"])

    assert result.exit_code == 0
    assert "t-1" in result.output


def test_projects_get_404_shows_friendly_error(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/999").return_value = httpx.Response(
            404, json={"error": {"code": "not_found", "message": "Project 999 no encontrado"}}
        )
        result = runner.invoke(app, ["projects", "get", "999"])

    assert result.exit_code != 0
    assert "404" in result.output or "no encontrado" in result.output


# ---------- campaigns ----------

def test_campaigns_launch_enqueues(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/campaigns/launch").return_value = httpx.Response(
            202,
            json={
                "task_id": "t-camp", "status": "queued",
                "sector": "rest", "region": "Madrid", "target_count": 50,
            },
        )
        result = runner.invoke(
            app,
            ["campaigns", "launch", "--sector", "rest", "--region", "Madrid"],
        )

    assert result.exit_code == 0
    assert "t-camp" in result.output


# ---------- error envelope mapping ----------

def test_api_connect_error_shows_hint(runner: CliRunner, authenticated, monkeypatch) -> None:
    """Sin respx mocking, httpx intenta conectar a api.test → ConnectError."""
    # Ningún router activo → connectError real
    result = runner.invoke(app, ["leads", "list"])
    assert result.exit_code != 0
    # CliConfigError lleva hint sobre uvicorn
    assert "uvicorn" in result.output or "API" in result.output
