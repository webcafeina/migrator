"""Tests del endpoint GET /api/v1/projects/{id}/summary — campo
`pages_with_many_unknowns` (ADR-052)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.lead_id = None
    return p


def _setup_basic_summary_mocks(fake_session, *, pages_unknown_count: int) -> None:
    """Configura los 5 awaitable execute() del endpoint summary."""
    fake_session.get = AsyncMock(return_value=_project_mock())

    # Construye 5 resultados mock para las 5 queries en orden:
    # 1) phase_rows GROUP BY status
    # 2) (opcional) phase_name si phases_running > 0 — saltado aquí (0 running)
    # 3) (opcional) phase_name última COMPLETED — saltado (0 completed)
    # 4) residual_rows
    # 5) pages_with_many_unknowns count
    phases_result = MagicMock()
    phases_result.all = MagicMock(return_value=[])  # 0 fases

    residual_result = MagicMock()
    residual_result.all = MagicMock(return_value=[])  # 0 residuales

    unknowns_result = MagicMock()
    unknowns_result.scalar_one = MagicMock(return_value=pages_unknown_count)

    fake_session.execute = AsyncMock(
        side_effect=[phases_result, residual_result, unknowns_result]
    )


@pytest.mark.asyncio
async def test_summary_devuelve_pages_with_many_unknowns_0(
    client, viewer_token, fake_session
) -> None:
    _setup_basic_summary_mocks(fake_session, pages_unknown_count=0)
    resp = await client.get("/api/v1/projects/7/summary", headers=_auth(viewer_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["pages_with_many_unknowns"] == 0


@pytest.mark.asyncio
async def test_summary_devuelve_pages_with_many_unknowns_3(
    client, viewer_token, fake_session
) -> None:
    _setup_basic_summary_mocks(fake_session, pages_unknown_count=3)
    resp = await client.get("/api/v1/projects/7/summary", headers=_auth(viewer_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["pages_with_many_unknowns"] == 3


@pytest.mark.asyncio
async def test_summary_404_si_proyecto_no_existe(
    client, viewer_token, fake_session
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/projects/99/summary", headers=_auth(viewer_token))
    assert resp.status_code == 404
