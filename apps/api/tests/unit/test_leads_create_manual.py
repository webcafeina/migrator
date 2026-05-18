"""Tests de los endpoints de alta manual de leads (v0.11.0):

- `POST /api/v1/leads` (single)
- `POST /api/v1/leads/bulk`

Foco: contrato + 409 + AuditLog con `legal_ground=6.1.f` + payload.source +
fire-and-forget de fingerprint+enrich. NO probamos integración con worker
real (mockeamos `enqueue_*` para verificar invocación).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_types.enums import LeadStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _lead_mock(*, lead_id: int = 1, url: str = "https://barpepe.es/") -> MagicMock:
    """Lead mock minimal para que `LeadRead.model_validate` lo digiera."""
    lead = MagicMock()
    lead.id = lead_id
    lead.url = url
    lead.business_name = None
    lead.sector = None
    lead.country = "ES"
    lead.region = None
    lead.status = LeadStatus.DISCOVERED
    lead.score = 0
    lead.builder_detected = None
    lead.builder_confidence = None
    lead.builder_evidence = None
    lead.emails = []
    lead.phones = []
    lead.social_links = {}
    lead.last_crawl_at = None
    lead.embedding_model = None
    lead.embedding_at = None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    lead.created_at = now
    lead.updated_at = now
    return lead


# ---------- POST /leads (single) ----------

@pytest.mark.asyncio
async def test_create_single_requires_operator(client, viewer_token) -> None:
    """Viewer no puede dar de alta leads — datos de procedencia + acción."""
    resp = await client.post(
        "/api/v1/leads",
        headers=_auth(viewer_token),
        json={"url": "https://barpepe.es"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_single_success_201_audit_and_enqueue(
    client, fake_session, operator_token
) -> None:
    """Happy path: 201 + AuditLog DISCOVER con legal_ground=6.1.f +
    payload.source=manual_single + ambas tasks Celery encoladas."""
    # 1ª execute: INSERT RETURNING id (lead creado)
    insert_result = MagicMock()
    insert_result.scalar_one_or_none = MagicMock(return_value=42)
    fake_session.execute = AsyncMock(side_effect=[insert_result])
    fake_session.get = AsyncMock(return_value=_lead_mock(lead_id=42))

    with (
        patch("wcm_api.routers.leads.enqueue_lead_fingerprint") as mock_fp,
        patch("wcm_api.routers.leads.enqueue_lead_enrich") as mock_en,
    ):
        mock_fp.return_value = "task-fp-1"
        mock_en.return_value = "task-en-1"
        resp = await client.post(
            "/api/v1/leads",
            headers=_auth(operator_token),
            json={
                "url": "https://barpepe.es",
                "sector": "restauración",
                "region": "Cáceres",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 42
    assert body["status"] == "discovered"

    # AuditLog: session.add fue llamado con un AuditLog con valores correctos.
    added = [call.args[0] for call in fake_session.add.call_args_list]
    audit_logs = [
        a for a in added
        if getattr(a, "entity_type", None) == "lead"
    ]
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.legal_ground == "6.1.f"
    assert audit.payload["source"] == "manual_single"
    assert audit.payload["operator_role"] == "operator"

    # Celery: ambas tasks encoladas con el lead_id correcto.
    mock_fp.assert_called_once_with(42)
    mock_en.assert_called_once_with(42, skip_embedding=False)


@pytest.mark.asyncio
async def test_create_single_normalizes_url(
    client, fake_session, operator_token
) -> None:
    """URL con www + querystring + trailing slash → persistida canónica
    sin esos elementos. Se verifica leyendo el VALUES del INSERT compilado.
    """
    insert_result = MagicMock()
    insert_result.scalar_one_or_none = MagicMock(return_value=7)
    fake_session.execute = AsyncMock(side_effect=[insert_result])
    fake_session.get = AsyncMock(return_value=_lead_mock(lead_id=7))

    with (
        patch("wcm_api.routers.leads.enqueue_lead_fingerprint"),
        patch("wcm_api.routers.leads.enqueue_lead_enrich"),
    ):
        resp = await client.post(
            "/api/v1/leads",
            headers=_auth(operator_token),
            json={"url": "https://www.Example.com/contacto/?utm_source=mail"},
        )

    assert resp.status_code == 201
    # El INSERT statement recibió la URL canónica (sin www, sin
    # querystring, sin trailing slash).
    insert_stmt = fake_session.execute.call_args_list[0].args[0]
    compiled = str(insert_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "https://example.com/contacto" in compiled
    assert "utm_source" not in compiled
    assert "www." not in compiled


@pytest.mark.asyncio
async def test_create_single_409_when_url_duplicate(
    client, fake_session, operator_token
) -> None:
    """Si la URL ya existe (RETURNING vacío), 409 con `existing_lead_id`
    en los details para que el dashboard pueda navegar al existente."""
    # 1ª execute: INSERT devuelve None (conflict)
    insert_result = MagicMock()
    insert_result.scalar_one_or_none = MagicMock(return_value=None)
    # 2ª execute: SELECT id del existente
    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=13)
    fake_session.execute = AsyncMock(side_effect=[insert_result, select_result])

    resp = await client.post(
        "/api/v1/leads",
        headers=_auth(operator_token),
        json={"url": "https://barpepe.es"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["details"]["existing_lead_id"] == 13


@pytest.mark.asyncio
async def test_create_single_422_when_url_malformed(
    client, operator_token
) -> None:
    """URL inválida cae en Pydantic antes de llegar al handler."""
    resp = await client.post(
        "/api/v1/leads",
        headers=_auth(operator_token),
        json={"url": "no es una url"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_single_celery_unavailable_still_returns_201(
    client, fake_session, operator_token
) -> None:
    """Si Celery falla al encolar, el lead persiste — fire-and-forget."""
    insert_result = MagicMock()
    insert_result.scalar_one_or_none = MagicMock(return_value=99)
    fake_session.execute = AsyncMock(side_effect=[insert_result])
    fake_session.get = AsyncMock(return_value=_lead_mock(lead_id=99))

    with (
        patch("wcm_api.routers.leads.enqueue_lead_fingerprint",
              side_effect=RuntimeError("broker down")),
        patch("wcm_api.routers.leads.enqueue_lead_enrich",
              side_effect=RuntimeError("broker down")),
    ):
        resp = await client.post(
            "/api/v1/leads",
            headers=_auth(operator_token),
            json={"url": "https://barpepe.es"},
        )
    # Lead persistido → 201, aunque Celery cayera.
    assert resp.status_code == 201


# ---------- POST /leads/bulk ----------

@pytest.mark.asyncio
async def test_bulk_requires_operator(client, viewer_token) -> None:
    resp = await client.post(
        "/api/v1/leads/bulk",
        headers=_auth(viewer_token),
        json={"urls": ["https://a.com"]},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_empty_urls_422(client, operator_token) -> None:
    resp = await client.post(
        "/api/v1/leads/bulk",
        headers=_auth(operator_token),
        json={"urls": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_too_many_urls_422(client, operator_token) -> None:
    urls = [f"https://site{i}.com" for i in range(201)]
    resp = await client.post(
        "/api/v1/leads/bulk",
        headers=_auth(operator_token),
        json={"urls": urls},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_mixed_outcomes(client, fake_session, operator_token) -> None:
    """3 URLs nuevas + 1 duplicada. La duplicada va a `skipped_duplicates`
    con `lead_id` del existente; las 3 nuevas a `created` con LeadRead
    completo. Encola fingerprint+enrich SOLO para las 3 creadas."""
    # Orden de execute por URL:
    #  URL1 → INSERT returns 101 (nuevo)
    #  URL2 → INSERT returns 102 (nuevo)
    #  URL3 → INSERT returns None (dup) → SELECT returns 50 (existente)
    #  URL4 → INSERT returns 103 (nuevo)
    def _ok(lead_id: int) -> MagicMock:
        m = MagicMock()
        m.scalar_one_or_none = MagicMock(return_value=lead_id)
        return m

    def _none() -> MagicMock:
        m = MagicMock()
        m.scalar_one_or_none = MagicMock(return_value=None)
        return m

    fake_session.execute = AsyncMock(side_effect=[
        _ok(101),
        _ok(102),
        _none(), _ok(50),  # URL3: insert=None, select=50
        _ok(103),
    ])
    fake_session.get = AsyncMock(side_effect=lambda model, lead_id: _lead_mock(lead_id=lead_id))

    with (
        patch("wcm_api.routers.leads.enqueue_lead_fingerprint") as mock_fp,
        patch("wcm_api.routers.leads.enqueue_lead_enrich") as mock_en,
    ):
        resp = await client.post(
            "/api/v1/leads/bulk",
            headers=_auth(operator_token),
            json={
                "urls": [
                    "https://nuevo1.com",
                    "https://nuevo2.com",
                    "https://dup.com",
                    "https://nuevo3.com",
                ],
                "sector": "restauración",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["created"]) == 3
    assert len(body["skipped_duplicates"]) == 1
    assert body["skipped_duplicates"][0]["lead_id"] == 50
    assert body["skipped_duplicates"][0]["outcome"] == "skipped_duplicate"
    assert len(body["failed"]) == 0
    # fingerprint + enrich SOLO para las 3 creadas.
    assert mock_fp.call_count == 3
    assert mock_en.call_count == 3


@pytest.mark.asyncio
async def test_bulk_audit_legal_ground_and_source(
    client, fake_session, operator_token
) -> None:
    """Cada lead creado en bulk genera un AuditLog con legal_ground=6.1.f
    y payload.source=manual_bulk + batch_size."""
    fake_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=200)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=201)),
    ])
    fake_session.get = AsyncMock(side_effect=lambda model, lead_id: _lead_mock(lead_id=lead_id))

    with (
        patch("wcm_api.routers.leads.enqueue_lead_fingerprint"),
        patch("wcm_api.routers.leads.enqueue_lead_enrich"),
    ):
        await client.post(
            "/api/v1/leads/bulk",
            headers=_auth(operator_token),
            json={"urls": ["https://a.com", "https://b.com"]},
        )

    audit_logs = [
        call.args[0] for call in fake_session.add.call_args_list
        if getattr(call.args[0], "entity_type", None) == "lead"
    ]
    assert len(audit_logs) == 2
    for audit in audit_logs:
        assert audit.legal_ground == "6.1.f"
        assert audit.payload["source"] == "manual_bulk"
        assert audit.payload["batch_size"] == 2
        assert audit.payload["operator_role"] == "operator"
