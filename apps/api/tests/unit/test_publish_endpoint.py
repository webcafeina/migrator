"""Tests del endpoint POST /api/v1/projects/{id}/publish (ADR-039 / v0.20.0)."""

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
    return p


@pytest.mark.asyncio
async def test_publish_404_si_proyecto_no_existe(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.post(
        "/api/v1/projects/99/publish", headers=_auth(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_409_si_status_no_permitido(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.RUNNING)
    )
    resp = await client.post(
        "/api/v1/projects/7/publish", headers=_auth(operator_token)
    )
    assert resp.status_code == 409
    body = resp.json()
    assert "completed" in body["error"]["message"]


@pytest.mark.asyncio
async def test_publish_happy_path_completed(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.COMPLETED)
    )
    with patch("wcm_api.routers.projects.enqueue_project_publish") as mock_enq:
        mock_enq.return_value = "task-publish-abc"
        resp = await client.post(
            "/api/v1/projects/7/publish", headers=_auth(operator_token)
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["task_id"] == "task-publish-abc"
    assert body["project_id"] == 7


@pytest.mark.asyncio
async def test_publish_happy_path_qa_failed(
    client, fake_session, operator_token
) -> None:
    """También permitido tras qa_failed — el operador a veces decide
    publicar aun con QA con warnings."""
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.QA_FAILED)
    )
    with patch("wcm_api.routers.projects.enqueue_project_publish") as mock_enq:
        mock_enq.return_value = "task-publish-xyz"
        resp = await client.post(
            "/api/v1/projects/7/publish", headers=_auth(operator_token)
        )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_publish_viewer_no_puede(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.COMPLETED)
    )
    resp = await client.post(
        "/api/v1/projects/7/publish", headers=_auth(viewer_token)
    )
    assert resp.status_code == 403
