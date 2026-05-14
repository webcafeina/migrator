"""Tests del rate limiting (Fase 15)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_api.rate_limit import limiter


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _enable_limiter_for_rate_tests():
    """En este módulo SÍ queremos el limiter activo. El conftest del API
    lo desactiva por defecto; aquí lo reactivamos y reseteamos buckets.
    """
    limiter.enabled = True
    # Reset duro del storage interno (MemoryStorage)
    storage = limiter._storage  # noqa: SLF001
    for attr in ("storage", "events", "expirations"):
        obj = getattr(storage, attr, None)
        if obj is not None and hasattr(obj, "clear"):
            obj.clear()
    yield
    limiter.enabled = False


@pytest.mark.asyncio
async def test_login_rate_limit_after_5_requests(client, fake_session) -> None:
    """6º intento de login en <1min debe responder 429."""
    # Simula `scalar_one_or_none()` síncrono devuelve None (usuario no encontrado).
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session.execute.return_value = exec_result

    payload = {"email": "x@y.com", "password": "pw"}
    # 5 primeros pasan (devuelven 401 por credenciales, el limiter NO bloquea)
    for i in range(5):
        resp = await client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code in (401, 422), f"intento {i + 1} → {resp.status_code}"

    # 6º intento debe ser bloqueado por rate limit
    resp = await client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_outreach_compose_rate_limit(client, fake_session, operator_token) -> None:
    """10º compose en <1min para el mismo lead debe responder 429."""
    lead = MagicMock()
    lead.id = 1
    lead.emails = ["x@y.com"]
    fake_session.get.return_value = lead

    from unittest.mock import patch

    with patch("wcm_api.routers.leads.enqueue_outreach_compose", return_value="t1"):
        # 10 primeros pasan
        for i in range(10):
            resp = await client.post(
                "/api/v1/leads/1/outreach/compose",
                headers=auth_headers(operator_token),
            )
            assert resp.status_code == 202, f"intento {i + 1} → {resp.status_code}"

        # 11º bloqueado
        resp = await client.post(
            "/api/v1/leads/1/outreach/compose",
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_health_endpoint_no_rate_limit(client) -> None:
    """`/health` NO está bajo rate limit — el probe Nginx debe poder
    martillar sin penalización.
    """
    for _ in range(20):
        resp = await client.get("/health")
        assert resp.status_code == 200
