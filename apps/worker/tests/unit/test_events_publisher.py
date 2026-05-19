"""Tests del publisher de eventos del worker (v0.19.0)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from wcm_worker.integrations.events import (
    CHANNEL_PREFIX,
    channel_for,
    publish_phase_event,
)


def test_channel_for() -> None:
    assert channel_for(7) == f"{CHANNEL_PREFIX}7:events"


def test_publish_sin_redis_url_no_hace_nada(monkeypatch) -> None:
    """Sin REDIS_URL no debe intentar importar redis ni publicar."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Si redis se importara, fallaría aquí; pero el helper retorna antes.
    publish_phase_event(7, "qa", "completed")


def test_publish_silencioso_si_redis_falla(monkeypatch) -> None:
    """Si Redis levanta excepción, publish_phase_event NO debe propagar."""
    monkeypatch.setenv("REDIS_URL", "redis://nope:1234/0")

    fake_redis_module = MagicMock()
    fake_redis_module.Redis.from_url.side_effect = RuntimeError("no reachable")
    with patch.dict("sys.modules", {"redis": fake_redis_module}):
        # No raise.
        publish_phase_event(7, "deploy_wp", "running")


def test_publish_happy_path_serializa_payload_correcto(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    fake_redis_module = MagicMock()
    fake_client = MagicMock()
    fake_redis_module.Redis.from_url.return_value = fake_client

    with patch.dict("sys.modules", {"redis": fake_redis_module}):
        publish_phase_event(
            7,
            "qa",
            "completed",
            summary="Lighthouse perf 92",
            extras={"residuals_created": 0},
        )

    fake_client.publish.assert_called_once()
    args, _ = fake_client.publish.call_args
    channel, raw = args
    assert channel == channel_for(7)
    payload = json.loads(raw)
    assert payload["kind"] == "phase"
    assert payload["project_id"] == 7
    assert payload["phase_name"] == "qa"
    assert payload["status"] == "completed"
    assert payload["summary"] == "Lighthouse perf 92"
    assert payload["residuals_created"] == 0
    assert "ts" in payload


def test_publish_trunca_summary_a_200_chars(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    fake_redis_module = MagicMock()
    fake_client = MagicMock()
    fake_redis_module.Redis.from_url.return_value = fake_client

    with patch.dict("sys.modules", {"redis": fake_redis_module}):
        publish_phase_event(7, "transpile_bricks", "completed", summary="x" * 500)

    args, _ = fake_client.publish.call_args
    payload = json.loads(args[1])
    assert len(payload["summary"]) == 200
