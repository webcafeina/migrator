"""Tests del endpoint POST /api/v1/projects/with-start (ADR-047 / v0.20.0).

Endpoint combinador para scripts/webhooks/integraciones. Crea proyecto +
opcionalmente ejecuta preflight + opcionalmente arranca.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from wcm_types.enums import ProjectStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _preflight_ok():
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    return PreflightResult(
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


def _preflight_blocking():
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    return PreflightResult(
        wp_target=PreflightCheck(
            ok=False, blocking=True, message="REST: HTTP 502"
        ),
        plugins={"bricks": False, "gravity_forms": True, "woocommerce": True},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=True, blocking=False, message="Sin credenciales"
        ),
        can_start=False,
        blocking_issues=["WP destino: REST: HTTP 502"],
        warnings=[],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )


def _setup_create_mocks(fake_session):
    """Mock para que el create_project funcione (session.add + commit + refresh)."""
    from datetime import UTC, datetime

    async def _refresh_side_effect(obj):
        obj.id = 1
        obj.status = ProjectStatus.QUEUED
        obj.created_at = datetime.now(UTC)
        obj.updated_at = datetime.now(UTC)
        obj.source_access_mode = "none"

    fake_session.refresh.side_effect = _refresh_side_effect


@pytest.mark.asyncio
async def test_happy_path_preflight_ok_arranca(
    client, operator_token, fake_session, monkeypatch
) -> None:
    _setup_create_mocks(fake_session)
    from wcm_api.routers import projects as projects_router

    async def _fake_pf(_p):
        return _preflight_ok()

    monkeypatch.setattr(projects_router, "run_preflight", _fake_pf)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enq:
        mock_enq.return_value = "task-with-start-123"
        resp = await client.post(
            "/api/v1/projects/with-start",
            json={
                "client_name": "Demo",
                "source_url": "https://demo.example/",
            },
            headers=_auth(operator_token),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task_id"] == "task-with-start-123"
    assert body["project_id"] == 1
    assert body["preflight"]["can_start"] is True


@pytest.mark.asyncio
async def test_preflight_bloqueante_409_y_no_arranca(
    client, operator_token, fake_session, monkeypatch
) -> None:
    _setup_create_mocks(fake_session)
    from wcm_api.routers import projects as projects_router

    async def _fake_pf(_p):
        return _preflight_blocking()

    monkeypatch.setattr(projects_router, "run_preflight", _fake_pf)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enq:
        resp = await client.post(
            "/api/v1/projects/with-start",
            json={
                "client_name": "Demo",
                "source_url": "https://demo.example/",
            },
            headers=_auth(operator_token),
        )
    assert resp.status_code == 409
    # NO se encoló nada
    mock_enq.assert_not_called()
    # El proyecto SÍ se creó (queda en queued)
    fake_session.add.assert_called()


@pytest.mark.asyncio
async def test_skip_preflight_arranca_directo(
    client, operator_token, fake_session, monkeypatch
) -> None:
    """skip_preflight=true salta el preflight (peligroso pero válido para scripts)."""
    _setup_create_mocks(fake_session)
    from wcm_api.routers import projects as projects_router

    async def _fake_pf(_p):
        raise AssertionError("preflight NO debería ejecutarse con skip_preflight=true")

    monkeypatch.setattr(projects_router, "run_preflight", _fake_pf)

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enq:
        mock_enq.return_value = "task-skipped"
        resp = await client.post(
            "/api/v1/projects/with-start",
            json={
                "client_name": "Demo",
                "source_url": "https://demo.example/",
                "skip_preflight": True,
            },
            headers=_auth(operator_token),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["preflight"] is None  # no se ejecutó
    assert body["task_id"] == "task-skipped"


@pytest.mark.asyncio
async def test_force_start_arranca_aunque_preflight_bloquee(
    client, operator_token, fake_session, monkeypatch
) -> None:
    """force_start=true arranca aunque preflight diga can_start=False."""
    _setup_create_mocks(fake_session)
    from wcm_api.routers import projects as projects_router

    async def _fake_pf(_p):
        return _preflight_blocking()

    monkeypatch.setattr(projects_router, "run_preflight", _fake_pf)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enq:
        mock_enq.return_value = "task-forced"
        resp = await client.post(
            "/api/v1/projects/with-start",
            json={
                "client_name": "Demo",
                "source_url": "https://demo.example/",
                "force_start": True,
            },
            headers=_auth(operator_token),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["preflight"]["can_start"] is False  # preflight reporta bloqueante
    assert body["task_id"] == "task-forced"  # pero arrancó igualmente


@pytest.mark.asyncio
async def test_payload_invalido_422(
    client, operator_token, fake_session
) -> None:
    """Sin client_name (campo obligatorio) → 422."""
    resp = await client.post(
        "/api/v1/projects/with-start",
        json={"source_url": "https://demo.example/"},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_403_viewer_no_puede_usar(
    client, viewer_token, fake_session
) -> None:
    resp = await client.post(
        "/api/v1/projects/with-start",
        json={
            "client_name": "Demo",
            "source_url": "https://demo.example/",
        },
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403
