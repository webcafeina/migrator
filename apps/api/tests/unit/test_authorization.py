"""Tests de role-based authorization."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_viewer_cannot_create_user(client, viewer_token) -> None:
    response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"email": "x@example.com", "name": "X", "password": "passw0rd1234"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_operator_cannot_list_users(client, operator_token) -> None:
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_token, fake_session) -> None:
    # Mock query: lista vacía
    from unittest.mock import MagicMock

    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=[])
    result.scalars = MagicMock(return_value=scalars)
    fake_session.execute.return_value = result

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_viewer_can_read_leads(client, viewer_token, fake_session) -> None:
    from unittest.mock import MagicMock

    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=[])
    result.scalars = MagicMock(return_value=scalars)
    fake_session.execute.return_value = result

    response = await client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_refingerprint_lead(client, viewer_token, fake_session) -> None:
    response = await client.post(
        "/api/v1/leads/1/refingerprint",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
