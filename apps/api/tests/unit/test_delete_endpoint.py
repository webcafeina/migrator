"""Tests del endpoint DELETE /api/v1/projects/{id} (ADR-054 / v0.20.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_types.enums import ProjectStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_status: ProjectStatus = ProjectStatus.COMPLETED) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.client_name = "Test"
    p.source_url = "https://t.es"
    p.target_domain = "t.com"
    p.status = project_status
    return p


@pytest.mark.asyncio
async def test_delete_401_sin_auth(client, fake_session) -> None:
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={"confirm": "DELETE PROJECT 7"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_403_operator(client, fake_session, operator_token) -> None:
    """Operator NO puede DELETE — admin-only."""
    fake_session.get = AsyncMock(return_value=_project_mock())
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={"confirm": "DELETE PROJECT 7"},
        headers=_auth(operator_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_404_si_proyecto_no_existe(
    client, fake_session, admin_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/99",
        json={"confirm": "DELETE PROJECT 99"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_409_sin_confirm(client, fake_session, admin_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409
    assert "DELETE PROJECT 7" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_delete_409_si_confirm_no_coincide(
    client, fake_session, admin_token
) -> None:
    """confirm con ID equivocado → 409 (protege contra borrar el incorrecto)."""
    fake_session.get = AsyncMock(return_value=_project_mock())
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={"confirm": "DELETE PROJECT 8"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_409_si_status_running(
    client, fake_session, admin_token
) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(project_status=ProjectStatus.RUNNING)
    )
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={"confirm": "DELETE PROJECT 7"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409
    assert "ejecución" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_delete_happy_path_204(
    client, fake_session, admin_token
) -> None:
    project = _project_mock()
    fake_session.get = AsyncMock(return_value=project)
    fake_session.delete = AsyncMock()
    fake_session.commit = AsyncMock()
    resp = await client.request(
        "DELETE",
        "/api/v1/projects/7",
        json={"confirm": "DELETE PROJECT 7"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204
    fake_session.delete.assert_awaited_once_with(project)
    fake_session.commit.assert_awaited_once()
