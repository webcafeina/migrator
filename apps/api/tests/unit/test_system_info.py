"""Tests de `GET /api/v1/system/info`.

Endpoint admin/operator que devuelve runtime: version, environment,
python_version, alembic_revision (de la BD), uptime, health summary.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wire(
    fake_session: MagicMock,
    *,
    alembic_revision: str | None,
    db_ok: bool = True,
) -> None:
    """Configura las 2 ejecuciones SQL del endpoint en orden:
    1) SELECT version_num FROM alembic_version
    2) SELECT 1  (health _check_db)

    Si `alembic_revision` es None, simula que la tabla no existe
    (Exception). Si `db_ok` es False, simula error en SELECT 1.
    """
    side_effects: list = []
    if alembic_revision is None:
        side_effects.append(RuntimeError("relation alembic_version does not exist"))
    else:
        result = MagicMock()
        result.first = MagicMock(return_value=(alembic_revision,))
        side_effects.append(result)

    if db_ok:
        side_effects.append(MagicMock())
    else:
        side_effects.append(RuntimeError("connection refused"))

    fake_session.execute = AsyncMock(side_effect=side_effects)


@pytest.fixture
def _patch_optional_checkers(monkeypatch):
    """Por defecto: redis y r2 a 'skipped' (no configurados en sandbox).
    Cada test puede sobreescribir con monkeypatch.setattr si lo
    necesita.
    """

    async def _redis_skip() -> dict:
        return {"status": "skipped", "reason": "test"}

    def _r2_skip() -> dict:
        return {"status": "skipped", "reason": "test"}

    monkeypatch.setattr("wcm_api.routers.system._check_redis", _redis_skip)
    monkeypatch.setattr("wcm_api.routers.system._check_r2", _r2_skip)


@pytest.mark.asyncio
async def test_info_shape_canonica(
    client, fake_session, operator_token, _patch_optional_checkers
) -> None:
    _wire(fake_session, alembic_revision="c8e1dc21716b")
    resp = await client.get("/api/v1/system/info", headers=_auth(operator_token))
    assert resp.status_code == 200
    data = resp.json()
    # Campos canónicos
    assert set(data.keys()) == {
        "version",
        "environment",
        "python_version",
        "alembic_revision",
        "uptime_seconds",
        "health",
    }
    assert data["alembic_revision"] == "c8e1dc21716b"
    assert data["environment"] == "development"
    assert data["uptime_seconds"] >= 0
    # python_version: X.Y.Z
    assert data["python_version"].count(".") == 2
    # version no vacía
    assert data["version"]
    # health: 4 campos canónicos
    assert set(data["health"].keys()) == {"overall", "db", "redis", "r2"}


@pytest.mark.asyncio
async def test_info_alembic_revision_null_si_tabla_no_existe(
    client, fake_session, operator_token, _patch_optional_checkers
) -> None:
    """Si la BD existe pero `alembic_version` no — caso de BD recién
    creada sin migraciones — devolvemos null, no 500."""
    _wire(fake_session, alembic_revision=None)
    resp = await client.get("/api/v1/system/info", headers=_auth(operator_token))
    assert resp.status_code == 200
    assert resp.json()["alembic_revision"] is None


@pytest.mark.asyncio
async def test_info_health_overall_degraded_si_r2_falla(
    client, fake_session, operator_token, monkeypatch
) -> None:
    """R2 es opcional — su fallo degrada el overall a 'degraded',
    no a 'fail' (el producto sigue funcional sin R2)."""

    async def _redis_ok() -> dict:
        return {"status": "ok", "latency_ms": 1.2}

    def _r2_fail() -> dict:
        return {"status": "fail", "error": "head_bucket: 403"}

    monkeypatch.setattr("wcm_api.routers.system._check_redis", _redis_ok)
    monkeypatch.setattr("wcm_api.routers.system._check_r2", _r2_fail)
    _wire(fake_session, alembic_revision="abc123")

    resp = await client.get("/api/v1/system/info", headers=_auth(operator_token))
    assert resp.status_code == 200
    h = resp.json()["health"]
    assert h == {"overall": "degraded", "db": "ok", "redis": "ok", "r2": "fail"}


@pytest.mark.asyncio
async def test_info_health_overall_fail_si_db_falla(
    client, fake_session, operator_token, monkeypatch
) -> None:
    """DB es crítica — su fallo lleva overall a 'fail'."""

    async def _redis_ok() -> dict:
        return {"status": "ok", "latency_ms": 1.0}

    def _r2_skip() -> dict:
        return {"status": "skipped", "reason": "test"}

    monkeypatch.setattr("wcm_api.routers.system._check_redis", _redis_ok)
    monkeypatch.setattr("wcm_api.routers.system._check_r2", _r2_skip)
    _wire(fake_session, alembic_revision="abc123", db_ok=False)

    resp = await client.get("/api/v1/system/info", headers=_auth(operator_token))
    assert resp.status_code == 200
    h = resp.json()["health"]
    assert h["overall"] == "fail"
    assert h["db"] == "fail"


@pytest.mark.asyncio
async def test_info_viewer_no_puede_leer(
    client, fake_session, viewer_token, _patch_optional_checkers
) -> None:
    """`/system/info` es admin/operator only: la revision Alembic y
    component paths pueden filtrar arquitectura interna."""
    resp = await client.get("/api/v1/system/info", headers=_auth(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_info_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code == 401
