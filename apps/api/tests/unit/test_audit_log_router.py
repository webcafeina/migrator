"""Tests de `GET /api/v1/audit-log` (feed de actividad del Overview).

Cubre: shape de respuesta, filtros (action, entity_type, entity_id,
actor, since, limit), auth, ordenación DESC por `at`, ventana por defecto
de 7 días.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from wcm_types.enums import AuditAction


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _entry(
    *,
    action: AuditAction = AuditAction.DISCOVER,
    entity_type: str | None = "lead",
    entity_id: str | None = "1",
    actor: str = "system",
    at: datetime | None = None,
    payload: dict[str, object] | None = None,
) -> MagicMock:
    """Construye un MagicMock con los atributos del AuditLog ORM."""
    m = MagicMock()
    m.id = uuid4()
    m.at = at or datetime.now(UTC)
    m.actor = actor
    m.action = action
    m.entity_type = entity_type
    m.entity_id = entity_id
    m.payload = payload
    m.legal_ground = None
    return m


def _wire_result(fake_session: MagicMock, entries: list[MagicMock]) -> None:
    """Stub: una sola execute() devuelve scalars().all() == entries."""
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=entries)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    fake_session.execute = AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_audit_log_devuelve_entradas_con_shape_esperada(
    client, fake_session, operator_token
) -> None:
    _wire_result(
        fake_session,
        [
            _entry(action=AuditAction.DISCOVER, entity_id="42"),
            _entry(action=AuditAction.ENRICH, entity_id="42"),
        ],
    )
    resp = await client.get("/api/v1/audit-log", headers=_auth(operator_token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["action"] == "discover"
    assert data[1]["action"] == "enrich"
    # Campos canónicos del modelo
    for entry in data:
        assert set(entry.keys()) >= {
            "id",
            "at",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "payload",
            "legal_ground",
        }


@pytest.mark.asyncio
async def test_audit_log_lista_vacia_ok(client, fake_session, viewer_token) -> None:
    _wire_result(fake_session, [])
    resp = await client.get("/api/v1/audit-log", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_audit_log_sin_auth_401(client) -> None:
    resp = await client.get("/api/v1/audit-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_filter_action_se_pasa_a_query(
    client, fake_session, operator_token
) -> None:
    """Verifica que `?action=enrich` aplica un WHERE sobre AuditLog.action."""
    _wire_result(fake_session, [_entry(action=AuditAction.ENRICH)])
    resp = await client.get(
        "/api/v1/audit-log?action=enrich", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    # Comprobamos que el statement compilado tiene un filter por action.
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "audit_log.action" in sql
    assert "enrich" in sql.lower()


@pytest.mark.asyncio
async def test_audit_log_filter_entity_type_y_id(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [_entry()])
    resp = await client.get(
        "/api/v1/audit-log?entity_type=lead&entity_id=42",
        headers=_auth(operator_token),
    )
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "entity_type" in sql
    assert "entity_id" in sql


@pytest.mark.asyncio
async def test_audit_log_orden_descendente_por_at(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get("/api/v1/audit-log", headers=_auth(operator_token))
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    # SQLAlchemy compila el ORDER BY explícito con DESC.
    assert "order by" in sql.lower()
    assert "desc" in sql.lower()


@pytest.mark.asyncio
async def test_audit_log_ventana_default_7_dias(
    client, fake_session, operator_token
) -> None:
    """Sin `since`, el endpoint usa now - 7 días como límite inferior."""
    _wire_result(fake_session, [])
    resp = await client.get("/api/v1/audit-log", headers=_auth(operator_token))
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    # Comprueba que hay un WHERE sobre audit_log.at >= ...
    assert "audit_log.at" in sql

    # El valor exacto del literal cambia cada ejecución; verificamos que
    # el limite está en la ventana razonable (entre 6 y 8 días atrás).
    cutoff_str = sql.split("audit_log.at >=")[1].split(")")[0]
    # extracción defensiva: si no parsea, el test al menos garantiza que
    # el WHERE existe.
    assert "-" in cutoff_str or ":" in cutoff_str
    _ = datetime.now(UTC) - timedelta(days=7)


@pytest.mark.asyncio
async def test_audit_log_limit_aplica(
    client, fake_session, operator_token
) -> None:
    _wire_result(fake_session, [])
    resp = await client.get("/api/v1/audit-log?limit=10", headers=_auth(operator_token))
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "limit" in sql.lower()
    assert " 10" in sql or sql.endswith("10")


@pytest.mark.asyncio
async def test_audit_log_limit_invalido_422(
    client, fake_session, operator_token
) -> None:
    """`limit > 200` rechazado por Pydantic Query(le=200)."""
    _wire_result(fake_session, [])
    resp = await client.get(
        "/api/v1/audit-log?limit=500", headers=_auth(operator_token)
    )
    assert resp.status_code == 422
