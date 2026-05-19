"""Tests de routers /projects, /leads y /campaigns (encolado Celery mockeado)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest


def _make_project_mock(project_id: int = 1, status_val: str = "queued"):
    p = MagicMock()
    p.id = project_id
    p.lead_id = None
    p.client_name = "Demo S.L."
    p.source_url = "https://demo.example/"
    p.target_domain = None
    p.builder_source = None
    p.has_ecommerce = False
    p.is_multilang = False
    p.langs = []
    p.primary_lang = None
    p.asset_storage = "wp_local"
    p.preserve_paths = True
    p.plan = None
    p.hosting_target_json = None
    p.theme_styles_origin = None
    p.visual_diff_avg_score = None
    p.status = status_val
    p.started_at = None
    p.completed_at = None
    p.estimated_go_live_at = None
    p.created_at = datetime.now(UTC)
    p.updated_at = datetime.now(UTC)
    return p


@pytest.mark.asyncio
async def test_create_project(client, operator_token, fake_session) -> None:
    from wcm_types.enums import ProjectStatus

    async def _refresh_side_effect(obj):
        # Simula los server defaults de Postgres (id autoincrement, timestamps, status)
        obj.id = 1
        obj.status = ProjectStatus.QUEUED
        obj.created_at = datetime.now(UTC)
        obj.updated_at = datetime.now(UTC)
        # v0.18.0 — server defaults nuevos
        obj.source_access_mode = "none"

    fake_session.refresh.side_effect = _refresh_side_effect

    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "client_name": "Demo S.L.",
            "source_url": "https://demo.example/",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["client_name"] == "Demo S.L."
    fake_session.commit.assert_awaited_once()
    fake_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_project_not_found(client, operator_token, fake_session) -> None:
    fake_session.get.return_value = None
    response = await client.get(
        "/api/v1/projects/999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_start_project_enqueues_job(
    client, operator_token, fake_session, monkeypatch
) -> None:
    """ADR-048: Start re-ejecuta preflight; can_start=True → arranca."""
    project = _make_project_mock(status_val="queued")
    fake_session.get.return_value = project

    from datetime import UTC, datetime

    from wcm_api.routers import projects as projects_router
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    fake_result = PreflightResult(
        wp_target=PreflightCheck(ok=True, blocking=True, message="WP OK"),
        plugins={"bricks": True, "gravity_forms": True, "woocommerce": True},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=True, blocking=False, message="Sin credenciales"
        ),
        can_start=True,
        blocking_issues=[],
        warnings=[],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    async def _fake_preflight(_p):
        return fake_result

    monkeypatch.setattr(projects_router, "run_preflight", _fake_preflight)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enqueue:
        mock_enqueue.return_value = "task-uuid-xyz"
        response = await client.post(
            "/api/v1/projects/1/start",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert response.status_code == 202
    assert response.json()["task_id"] == "task-uuid-xyz"
    mock_enqueue.assert_called_once_with(1, resume=False)


@pytest.mark.asyncio
async def test_adr048_start_bloquea_si_preflight_no_can_start(
    client, operator_token, fake_session, monkeypatch
) -> None:
    """ADR-048: Start con preflight bloqueante → 409, NO arranca."""
    project = _make_project_mock(status_val="queued")
    fake_session.get.return_value = project

    from datetime import UTC, datetime

    from wcm_api.routers import projects as projects_router
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    fake_result = PreflightResult(
        wp_target=PreflightCheck(
            ok=False, blocking=True, message="REST: HTTP 502; SSH: timeout"
        ),
        plugins={"bricks": False, "gravity_forms": True, "woocommerce": True},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=True, blocking=False, message="Sin credenciales"
        ),
        can_start=False,
        blocking_issues=["WP destino: REST: HTTP 502; SSH: timeout"],
        warnings=[],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    async def _fake_preflight(_p):
        return fake_result

    monkeypatch.setattr(projects_router, "run_preflight", _fake_preflight)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enqueue:
        response = await client.post(
            "/api/v1/projects/1/start",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert response.status_code == 409
    body = response.json()
    assert "Preflight bloqueante" in body["error"]["message"]
    assert "REST: HTTP 502" in body["error"]["message"]
    # NO se encoló el pipeline
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_start_project_already_running_returns_409(client, operator_token, fake_session) -> None:
    from wcm_types.enums import ProjectStatus

    project = _make_project_mock()
    project.status = ProjectStatus.RUNNING
    fake_session.get.return_value = project

    response = await client.post(
        "/api/v1/projects/1/start",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_launch_campaign_enqueues_job(client, operator_token) -> None:
    """El task_id es UUID v4 generado por el endpoint (no por Celery) para
    evitar race condition con el worker. Se pasa a enqueue como kwarg."""
    with patch("wcm_api.routers.campaigns.enqueue_prospect_campaign") as mock_enqueue:
        response = await client.post(
            "/api/v1/campaigns/launch",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={"sector": "restauración", "region": "Andalucía", "target_count": 20},
        )

    assert response.status_code == 202
    body = response.json()
    # UUID v4 (36 chars con 4 guiones)
    assert len(body["task_id"]) == 36
    assert body["task_id"].count("-") == 4
    mock_enqueue.assert_called_once()
    # El task_id se inyecta como kwarg para que celery.send_task lo fuerce
    assert mock_enqueue.call_args.kwargs.get("task_id") == body["task_id"]


@pytest.mark.asyncio
async def test_launch_campaign_validates_target_count(client, operator_token) -> None:
    response = await client.post(
        "/api/v1/campaigns/launch",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"sector": "x", "region": "y", "target_count": 999},  # > 500
    )
    assert response.status_code == 422  # FastAPI validation
