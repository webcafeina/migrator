"""Tests del endpoint público /opt-out (RGPD)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_api.security import issue_opt_out_token


def _mock_scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


@pytest.mark.asyncio
async def test_opt_out_invalid_token_rejected(client) -> None:
    response = await client.get("/opt-out?token=not-a-valid-token")
    # decode_opt_out_token levanta UnauthorizedError → mapeado a 401
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_opt_out_session_token_rejected(client, admin_token) -> None:
    """Un session token JWT no debe pasar como opt-out (purpose distinto)."""
    response = await client.get(f"/opt-out?token={admin_token}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_opt_out_valid_token_registers_and_shows_html(client, fake_session) -> None:
    token = issue_opt_out_token(email="user@example.com", lead_id=99)
    # No existe opt_out previo, ni lead — escenario de doble idempotencia
    fake_session.execute.return_value = _mock_scalar_one_or_none(None)
    fake_session.get.return_value = None

    response = await client.get(f"/opt-out?token={token}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "Baja registrada" in body
    assert "Webcafeína" in body
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_opt_out_idempotent_when_already_optouted(client, fake_session) -> None:
    """Si ya hay opt_out_log para ese email, no insertar duplicado pero
    devolver 200 OK al receptor (idempotente)."""
    token = issue_opt_out_token(email="user@example.com")

    existing_optout = MagicMock()
    fake_session.execute.return_value = _mock_scalar_one_or_none(existing_optout)
    fake_session.get.return_value = None

    response = await client.get(f"/opt-out?token={token}")
    assert response.status_code == 200
    # No se llamó a session.add para el opt-out (porque ya existe)
    fake_session.add.assert_not_called()
