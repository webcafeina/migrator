"""Tests del endpoint POST /api/v1/projects/{id}/rollback (v0.19.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_types.enums import ProjectStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_status: ProjectStatus) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.status = project_status
    return p


@pytest.mark.asyncio
async def test_404_si_proyecto_no_existe(client, fake_session, operator_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.post(
        "/api/v1/projects/99/rollback",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_409_si_sin_confirm(client, fake_session, operator_token) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.QA_FAILED)
    )
    resp = await client.post(
        "/api/v1/projects/7/rollback",
        json={},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 409
    assert "confirm" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_409_si_status_no_permitido(
    client, fake_session, operator_token
) -> None:
    """En status=running el rollback NO se permite."""
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.RUNNING)
    )
    resp = await client.post(
        "/api/v1/projects/7/rollback",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 409
    assert "running" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_happy_path_qa_failed_encola_task(
    client, fake_session, operator_token, monkeypatch
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.QA_FAILED)
    )

    sent: dict[str, object] = {}

    def _fake_enqueue(pid: int) -> str:
        sent["project_id"] = pid
        return "task-rollback-123"

    monkeypatch.setattr(
        "wcm_api.routers.projects.enqueue_project_rollback", _fake_enqueue
    )

    resp = await client.post(
        "/api/v1/projects/7/rollback",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["task_id"] == "task-rollback-123"
    assert body["project_id"] == 7
    assert sent["project_id"] == 7


@pytest.mark.asyncio
async def test_happy_path_completed_permite_rollback(
    client, fake_session, operator_token, monkeypatch
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.COMPLETED)
    )
    monkeypatch.setattr(
        "wcm_api.routers.projects.enqueue_project_rollback",
        lambda pid: "task-x",
    )
    resp = await client.post(
        "/api/v1/projects/7/rollback",
        json={"confirm": True},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_viewer_no_puede_rollback(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.QA_FAILED)
    )
    resp = await client.post(
        "/api/v1/projects/7/rollback",
        json={"confirm": True},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403
