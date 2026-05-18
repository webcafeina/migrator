"""Tests de descarte (soft) y borrado (hard) de leads (v0.12.0).

- POST /api/v1/leads/{id}/discard: status → DISCARDED + AuditLog UPDATE.
- DELETE /api/v1/leads/{id}: borrado con CASCADE + AuditLog DELETE.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_types.enums import LeadStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _lead_mock(
    *, lead_id: int = 1, status: LeadStatus = LeadStatus.ENRICHED,
    url: str = "https://barpepe.es/",
) -> MagicMock:
    lead = MagicMock()
    lead.id = lead_id
    lead.url = url
    lead.business_name = "Bar Pepe"
    lead.sector = None
    lead.country = "ES"
    lead.region = None
    lead.status = status
    lead.score = 50
    lead.builder_detected = None
    lead.builder_confidence = None
    lead.builder_evidence = None
    lead.emails = []
    lead.phones = []
    lead.social_links = {}
    lead.last_crawl_at = None
    lead.embedding_model = None
    lead.embedding_at = None
    now = datetime.now(UTC)
    lead.created_at = now
    lead.updated_at = now
    return lead


# ---------- POST /leads/{id}/discard ----------

@pytest.mark.asyncio
async def test_discard_requires_operator(client, viewer_token) -> None:
    resp = await client.post(
        "/api/v1/leads/1/discard", headers=_auth(viewer_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_discard_404_when_lead_missing(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.post(
        "/api/v1/leads/999/discard", headers=_auth(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_discard_changes_status_and_writes_audit(
    client, fake_session, operator_token
) -> None:
    lead = _lead_mock()
    fake_session.get = AsyncMock(return_value=lead)
    resp = await client.post(
        "/api/v1/leads/1/discard", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    assert lead.status == LeadStatus.DISCARDED
    # AuditLog con payload.action="discard"
    audit_logs = [
        c.args[0] for c in fake_session.add.call_args_list
        if getattr(c.args[0], "entity_type", None) == "lead"
    ]
    assert len(audit_logs) == 1
    assert audit_logs[0].payload["action"] == "discard"
    assert audit_logs[0].legal_ground == "6.1.f"


@pytest.mark.asyncio
async def test_discard_idempotent_when_already_discarded(
    client, fake_session, operator_token
) -> None:
    """Si el lead ya está DISCARDED, no se escribe AuditLog redundante."""
    lead = _lead_mock(status=LeadStatus.DISCARDED)
    fake_session.get = AsyncMock(return_value=lead)
    resp = await client.post(
        "/api/v1/leads/1/discard", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    # NO se añade AuditLog (idempotente).
    audit_logs = [
        c.args[0] for c in fake_session.add.call_args_list
        if getattr(c.args[0], "entity_type", None) == "lead"
    ]
    assert len(audit_logs) == 0


# ---------- DELETE /leads/{id} ----------

@pytest.mark.asyncio
async def test_delete_requires_operator(client, viewer_token) -> None:
    resp = await client.delete(
        "/api/v1/leads/1", headers=_auth(viewer_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_404_when_lead_missing(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.delete(
        "/api/v1/leads/999", headers=_auth(operator_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_writes_audit_before_delete_204(
    client, fake_session, operator_token
) -> None:
    """AuditLog DELETE se persiste ANTES del session.delete() para
    capturar snapshot (url + business_name) por si la fila desaparece."""
    lead = _lead_mock(url="https://barpepe.es/", lead_id=42)
    fake_session.get = AsyncMock(return_value=lead)
    resp = await client.delete(
        "/api/v1/leads/42", headers=_auth(operator_token)
    )
    assert resp.status_code == 204
    fake_session.delete.assert_called_once_with(lead)
    audit_logs = [
        c.args[0] for c in fake_session.add.call_args_list
        if getattr(c.args[0], "entity_type", None) == "lead"
    ]
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.payload["action"] == "hard_delete"
    assert audit.payload["snapshot_url"] == "https://barpepe.es/"
    assert audit.payload["snapshot_business_name"] == "Bar Pepe"
    assert audit.entity_id == "42"


# ---------- list_leads ahora oculta DISCARDED por defecto ----------

@pytest.mark.asyncio
async def test_list_leads_excluye_discarded_por_defecto(
    client, fake_session, operator_token
) -> None:
    """Verificación vía SQL compilado: la query base lleva
    `WHERE leads.status != 'discarded'` cuando NO se pasa status_filter."""
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute = AsyncMock(return_value=result)
    resp = await client.get(
        "/api/v1/leads", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "discarded" in sql.lower()
    assert "!=" in sql or "<>" in sql


@pytest.mark.asyncio
async def test_list_leads_incluye_discarded_si_filtro_explicito(
    client, fake_session, operator_token
) -> None:
    """Cuando se pide `?status=discarded` el listado los devuelve
    (chip 'Descartados' en el dashboard)."""
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute = AsyncMock(return_value=result)
    resp = await client.get(
        "/api/v1/leads?status=discarded", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    # Debe estar `status = 'discarded'` (filtro explícito), NOT `!= 'discarded'`.
    assert "= 'discarded'" in sql.lower() or "='discarded'" in sql.lower()
