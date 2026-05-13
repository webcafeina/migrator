"""Tests del endpoint /health/deep con mocks de dependencias."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_deep_db_ok_redis_skipped_r2_skipped(
    client, fake_session, monkeypatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("R2_BUCKET", raising=False)
    fake_session.execute.return_value = MagicMock()

    resp = await client.get("/health/deep")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["checks"]["db"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "skipped"
    assert body["checks"]["r2"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_health_deep_db_fail_returns_fail(client, fake_session, monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("R2_BUCKET", raising=False)
    fake_session.execute.side_effect = RuntimeError("connection refused")

    resp = await client.get("/health/deep")
    body = resp.json()
    assert body["status"] == "fail"
    assert body["checks"]["db"]["status"] == "fail"


@pytest.mark.asyncio
async def test_health_deep_redis_ok_when_ping_succeeds(
    client, fake_session, monkeypatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.delenv("R2_BUCKET", raising=False)
    fake_session.execute.return_value = MagicMock()

    fake_redis = MagicMock()
    fake_redis.ping = AsyncMock(return_value=True)
    fake_redis.aclose = AsyncMock(return_value=None)

    with patch("redis.asyncio.Redis.from_url", return_value=fake_redis):
        resp = await client.get("/health/deep")

    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_deep_redis_fail_marks_overall_fail(
    client, fake_session, monkeypatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.delenv("R2_BUCKET", raising=False)
    fake_session.execute.return_value = MagicMock()

    fake_redis = MagicMock()
    fake_redis.ping = AsyncMock(side_effect=RuntimeError("conn refused"))
    fake_redis.aclose = AsyncMock(return_value=None)

    with patch("redis.asyncio.Redis.from_url", return_value=fake_redis):
        resp = await client.get("/health/deep")
    body = resp.json()
    assert body["status"] == "fail"
    assert body["checks"]["redis"]["status"] == "fail"


@pytest.mark.asyncio
async def test_health_deep_r2_fail_marks_degraded(client, fake_session, monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("R2_BUCKET", "bk")
    monkeypatch.setenv("R2_ACCOUNT_ID", "a")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")
    fake_session.execute.return_value = MagicMock()

    fake_s3 = MagicMock()
    fake_s3.head_bucket.side_effect = RuntimeError("forbidden")

    # Inyectamos un R2Client cuyo _s3 falle. La función _check_r2 usa
    # R2Client.from_env() así que parcheamos eso.
    from wcm_worker.integrations.r2 import R2Client

    fake_client = R2Client(
        account_id="a", access_key_id="k", secret_access_key="s",
        bucket="bk", s3_client=fake_s3,
    )

    with patch.object(R2Client, "from_env", classmethod(lambda cls: fake_client)):
        resp = await client.get("/health/deep")
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["r2"]["status"] == "fail"
    assert body["checks"]["db"]["status"] == "ok"
