"""Tests del router /api/v1/auth."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from wcm_types.enums import UserRole

from wcm_api.security import hash_password


def _make_user_row(*, email: str = "test@webcafeina.com", password: str = "test1234", role=UserRole.ADMIN, active: bool = True):
    """Crea un mock User con los campos que el router necesita."""
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = email
    u.name = "Test User"
    u.role = role
    u.is_active = active
    u.hashed_password = hash_password(password)
    from datetime import datetime, timezone
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _mock_scalar_one_or_none(value):
    """Helper para configurar session.execute().scalar_one_or_none() = value."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


@pytest.mark.asyncio
async def test_login_success_sets_cookie(client, fake_session) -> None:
    user = _make_user_row(email="ok@webcafeina.com", password="passw0rd!")
    fake_session.execute.return_value = _mock_scalar_one_or_none(user)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ok@webcafeina.com", "password": "passw0rd!"},
    )
    assert response.status_code == 200
    assert "wcm_session" in response.cookies
    data = response.json()
    assert data["email"] == "ok@webcafeina.com"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, fake_session) -> None:
    user = _make_user_row(password="correct-password")
    fake_session.execute.return_value = _mock_scalar_one_or_none(user)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@webcafeina.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_login_email_not_found_returns_same_401(client, fake_session) -> None:
    """Anti-enumeración: mismo mensaje que password incorrecto."""
    fake_session.execute.return_value = _mock_scalar_one_or_none(None)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "x"},
    )
    assert response.status_code == 401
    assert "Credenciales" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_inactive_user_returns_401(client, fake_session) -> None:
    user = _make_user_row(password="x", active=False)
    fake_session.execute.return_value = _mock_scalar_one_or_none(user)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@webcafeina.com", "password": "x"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_with_token(client, fake_session, admin_token) -> None:
    """Con token válido, /me devuelve el usuario asociado."""
    user = _make_user_row()
    fake_session.get.return_value = user

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@webcafeina.com"


@pytest.mark.asyncio
async def test_logout_clears_cookie(client) -> None:
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    # Set-Cookie con max-age=0 o expires en el pasado
    cookies_header = response.headers.get("set-cookie", "")
    assert "wcm_session" in cookies_header
