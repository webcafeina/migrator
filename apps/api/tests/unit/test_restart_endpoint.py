"""Tests del endpoint POST /api/v1/projects/{id}/restart (ADR-041 / v0.20.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_types.enums import ProjectStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_status: ProjectStatus) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.status = project_status
    p.started_at = None
    p.completed_at = None
    return p


@pytest.mark.asyncio
async def test_restart_404_si_proyecto_no_existe(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.post(
        "/api/v1/projects/99/restart",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restart_409_sin_confirm(client, fake_session, operator_token) -> None:
    resp = await client.post(
        "/api/v1/projects/7/restart",
        json={},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 409
    assert "confirm" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_restart_409_si_status_no_es_rolled_back(
    client, fake_session, operator_token
) -> None:
    """Si status=completed, restart no aplica → 409."""
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.COMPLETED)
    )
    resp = await client.post(
        "/api/v1/projects/7/restart",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 409
    assert "rolled_back" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_restart_happy_path(
    client, fake_session, operator_token
) -> None:
    project = _project_mock(project_status=ProjectStatus.ROLLED_BACK)
    fake_session.get = AsyncMock(return_value=project)
    fake_session.commit = AsyncMock()

    with patch("wcm_api.routers.projects.enqueue_project_pipeline") as mock_enq:
        mock_enq.return_value = "task-restart-abc"
        resp = await client.post(
            "/api/v1/projects/7/restart",
            json={"confirm": True},
            headers=_auth(operator_token),
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["task_id"] == "task-restart-abc"
    assert body["restarted"] is True
    # El project se actualizó a QUEUED y timestamps reset.
    assert project.status == ProjectStatus.QUEUED
    assert project.started_at is None
    assert project.completed_at is None


@pytest.mark.asyncio
async def test_restart_viewer_no_puede(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.ROLLED_BACK)
    )
    resp = await client.post(
        "/api/v1/projects/7/restart",
        json={"confirm": True},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403
