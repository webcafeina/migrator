"""Tests de `GET /api/v1/projects/{id}/summary`.

Cubre: shape, lead_origin (con/sin lead_id), counts de fases por status,
current_phase_name (RUNNING > último COMPLETED > None), counts de
residual_tasks (open = total - done - skipped), 404, 401.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_types.enums import (
    BuilderType,
    ProjectPhaseStatus,
    ResidualStatus,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project(*, id: int = 1, lead_id: int | None = None) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.lead_id = lead_id
    return p


def _lead(*, id: int = 1, business_name: str | None = "Bar Pepe",
          score: int = 75, builder: BuilderType | None = BuilderType.WIX) -> MagicMock:
    l = MagicMock()
    l.id = id
    l.business_name = business_name
    l.score = score
    l.builder_detected = builder
    return l


def _wire(
    fake_session: MagicMock,
    *,
    project: MagicMock | None,
    lead: MagicMock | None = None,
    phase_rows: list[tuple[ProjectPhaseStatus, int]] | None = None,
    current_phase_running: str | None = None,
    current_phase_completed: str | None = None,
    residual_rows: list[tuple[ResidualStatus, int]] | None = None,
) -> None:
    """Configura `session.get` (project + lead) y `session.execute`
    (phase counts + current_phase + residual counts)."""
    # session.get devuelve project la primera vez, lead la segunda
    get_returns = [project]
    if project is not None and project.lead_id is not None:
        get_returns.append(lead)
    fake_session.get = AsyncMock(side_effect=get_returns)

    # execute: phase counts → (opcional) current_phase → residual counts
    execute_results: list[MagicMock] = []

    # Phase counts
    rows_mock = MagicMock()
    rows_mock.all = MagicMock(return_value=phase_rows or [])
    execute_results.append(rows_mock)

    # current_phase (solo si phases_running > 0 o phases_completed > 0)
    has_running = any(
        s == ProjectPhaseStatus.RUNNING and c > 0 for s, c in (phase_rows or [])
    )
    has_completed = any(
        s == ProjectPhaseStatus.COMPLETED and c > 0
        for s, c in (phase_rows or [])
    )
    if has_running:
        cp = MagicMock()
        cp.scalar_one_or_none = MagicMock(return_value=current_phase_running)
        execute_results.append(cp)
    elif has_completed:
        cp = MagicMock()
        cp.scalar_one_or_none = MagicMock(return_value=current_phase_completed)
        execute_results.append(cp)

    # Residual counts
    res_mock = MagicMock()
    res_mock.all = MagicMock(return_value=residual_rows or [])
    execute_results.append(res_mock)

    fake_session.execute = AsyncMock(side_effect=execute_results)


@pytest.mark.asyncio
async def test_summary_proyecto_sin_lead_ni_fases(
    client, fake_session, operator_token
) -> None:
    """Proyecto recién creado sin pipeline arrancado."""
    _wire(
        fake_session,
        project=_project(lead_id=None),
        phase_rows=[],
        residual_rows=[],
    )
    resp = await client.get(
        "/api/v1/projects/1/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == 1
    assert data["lead_origin"] is None
    assert data["phases_total"] == 0
    assert data["phases_completed"] == 0
    assert data["phases_running"] == 0
    assert data["current_phase_name"] is None
    assert data["residual_total"] == 0
    assert data["residual_open"] == 0
    assert data["residual_done"] == 0


@pytest.mark.asyncio
async def test_summary_con_lead_origen(
    client, fake_session, operator_token
) -> None:
    _wire(
        fake_session,
        project=_project(id=7, lead_id=42),
        lead=_lead(id=42, business_name="Hostel Papy", score=88, builder=BuilderType.WORDPRESS),
        phase_rows=[],
        residual_rows=[],
    )
    resp = await client.get(
        "/api/v1/projects/7/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    lead = resp.json()["lead_origin"]
    assert lead == {
        "id": 42,
        "business_name": "Hostel Papy",
        "score": 88,
        "builder_detected": "wordpress",
    }


@pytest.mark.asyncio
async def test_summary_lead_borrado_devuelve_null(
    client, fake_session, operator_token
) -> None:
    """`lead_id` apunta a un lead que ya no existe (ondelete=SET NULL
    no aplicó porque el delete fue manual)."""
    _wire(
        fake_session,
        project=_project(lead_id=99),
        lead=None,
        phase_rows=[],
        residual_rows=[],
    )
    resp = await client.get(
        "/api/v1/projects/1/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    assert resp.json()["lead_origin"] is None


@pytest.mark.asyncio
async def test_summary_phases_running_es_current(
    client, fake_session, operator_token
) -> None:
    """Si hay fase RUNNING, `current_phase_name` es esa (no la última
    completed)."""
    _wire(
        fake_session,
        project=_project(),
        phase_rows=[
            (ProjectPhaseStatus.COMPLETED, 5),
            (ProjectPhaseStatus.RUNNING, 1),
            (ProjectPhaseStatus.PENDING, 9),
        ],
        current_phase_running="scrape_origin",
        residual_rows=[],
    )
    resp = await client.get(
        "/api/v1/projects/1/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["phases_total"] == 15
    assert data["phases_completed"] == 5
    assert data["phases_running"] == 1
    assert data["phases_pending"] == 9
    assert data["current_phase_name"] == "scrape_origin"


@pytest.mark.asyncio
async def test_summary_sin_running_devuelve_ultima_completed(
    client, fake_session, operator_token
) -> None:
    _wire(
        fake_session,
        project=_project(),
        phase_rows=[(ProjectPhaseStatus.COMPLETED, 3)],
        current_phase_completed="content_extractor",
        residual_rows=[],
    )
    resp = await client.get(
        "/api/v1/projects/1/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    assert resp.json()["current_phase_name"] == "content_extractor"


@pytest.mark.asyncio
async def test_summary_residual_open_excluye_done_y_skipped(
    client, fake_session, operator_token
) -> None:
    """`open = total - done - skipped`. IN_PROGRESS y BLOCKED cuentan
    como open porque el operador aún tiene que tocarlos."""
    _wire(
        fake_session,
        project=_project(),
        phase_rows=[],
        residual_rows=[
            (ResidualStatus.OPEN, 4),
            (ResidualStatus.IN_PROGRESS, 2),
            (ResidualStatus.BLOCKED, 1),
            (ResidualStatus.DONE, 3),
            (ResidualStatus.SKIPPED, 1),
        ],
    )
    resp = await client.get(
        "/api/v1/projects/1/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["residual_total"] == 11
    assert data["residual_done"] == 3
    # open = 11 - 3 (done) - 1 (skipped) = 7
    assert data["residual_open"] == 7


@pytest.mark.asyncio
async def test_summary_404_si_proyecto_no_existe(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get(
        "/api/v1/projects/999/summary", headers=_auth(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/projects/1/summary")
    assert resp.status_code == 401
