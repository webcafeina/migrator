"""Tests del endpoint POST /api/v1/projects/{id}/preflight (v0.18.0).

Mockea los 4 chequeos individuales del servicio `preflight` para
verificar el agregado: blocking_issues, warnings, can_start, persistencia
en projects.preflight_results_json + preflight_at.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_id: int = 7) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.source_url = "https://origen.test"
    p.source_access_mode = "none"
    p.source_credentials_encrypted = None
    p.builder_source = None
    return p


def _check(ok: bool, blocking: bool = False, message: str = "ok", extras: dict | None = None) -> dict:
    return {"ok": ok, "blocking": blocking, "message": message, "extras": extras}


@pytest.mark.asyncio
async def test_404_si_proyecto_no_existe(client, fake_session, operator_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.post("/api/v1/projects/99/preflight", headers=_auth(operator_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_401_sin_auth(client, fake_session) -> None:
    resp = await client.post("/api/v1/projects/7/preflight")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_viewer_no_puede_ejecutar_preflight(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    resp = await client.post("/api/v1/projects/7/preflight", headers=_auth(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_happy_path_persiste_resultado(
    client, fake_session, operator_token, monkeypatch
) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    fake_session.commit = AsyncMock()

    # Mockear run_preflight para evitar tocar red real.
    from wcm_api.routers import projects as projects_router
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    fake_result = PreflightResult(
        wp_target=PreflightCheck(ok=True, blocking=True, message="WP OK"),
        plugins={"bricks": True, "gravity_forms": True, "woocommerce": False},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=True, blocking=False, message="Sin credenciales (modo público)."
        ),
        can_start=True,
        blocking_issues=[],
        warnings=["Plugin woocommerce no detectado en destino"],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    async def _fake_run(_project):
        return fake_result

    monkeypatch.setattr(projects_router, "run_preflight", _fake_run)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    resp = await client.post("/api/v1/projects/7/preflight", headers=_auth(operator_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_start"] is True
    assert body["wp_target"]["ok"] is True
    assert body["plugins"]["woocommerce"] is False
    assert "woocommerce" in body["warnings"][0]
    # commit fue llamado y el project recibió preflight_results_json.
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_preflight_bloquea_si_wp_no_accesible(
    client, fake_session, operator_token, monkeypatch
) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    fake_session.commit = AsyncMock()

    from wcm_api.routers import projects as projects_router
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    fake_result = PreflightResult(
        wp_target=PreflightCheck(
            ok=False, blocking=True, message="REST: HTTP 502; SSH: timeout"
        ),
        plugins={"bricks": False, "gravity_forms": False, "woocommerce": False},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=True, blocking=False, message="Sin credenciales"
        ),
        can_start=False,
        blocking_issues=["WP destino: REST: HTTP 502; SSH: timeout"],
        warnings=[],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    async def _fake_run(_project):
        return fake_result

    monkeypatch.setattr(projects_router, "run_preflight", _fake_run)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    resp = await client.post("/api/v1/projects/7/preflight", headers=_auth(operator_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_start"] is False
    assert "WP destino" in body["blocking_issues"][0]


@pytest.mark.asyncio
async def test_preflight_warning_si_credenciales_invalidas(
    client, fake_session, operator_token, monkeypatch
) -> None:
    """Credenciales inválidas → warning, NO bloquea (cae a Playwright)."""
    fake_session.get = AsyncMock(return_value=_project_mock())
    fake_session.commit = AsyncMock()

    from wcm_api.routers import projects as projects_router
    from wcm_types.schemas.projects import PreflightCheck, PreflightResult

    fake_result = PreflightResult(
        wp_target=PreflightCheck(ok=True, blocking=True, message="WP OK"),
        plugins={"bricks": True, "gravity_forms": True, "woocommerce": False},
        source=PreflightCheck(ok=True, blocking=True, message="Origen OK"),
        source_credentials=PreflightCheck(
            ok=False,
            blocking=False,
            message="Wix API rechaza credenciales (HTTP 401).",
            extras={"checked": True, "status_code": 401},
        ),
        can_start=True,
        blocking_issues=[],
        warnings=["Credenciales origen: Wix API rechaza credenciales (HTTP 401)."],
        executed_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    async def _fake_run(_project):
        return fake_result

    monkeypatch.setattr(projects_router, "run_preflight", _fake_run)
    monkeypatch.setattr(projects_router, "serialize_preflight_for_db", lambda r: {})

    resp = await client.post("/api/v1/projects/7/preflight", headers=_auth(operator_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_start"] is True
    assert any("Credenciales" in w for w in body["warnings"])
