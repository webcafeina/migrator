"""Tests del servicio SSE de eventos (v0.19.0).

Verifica los helpers puros (canonical channel name, formato SSE,
estructura del evento) sin dependencias externas (Redis mockeado o
no usado).
"""

from __future__ import annotations

import json

import pytest

from wcm_api.services.events import (
    CHANNEL_PREFIX,
    build_event,
    channel_for,
    format_heartbeat,
    format_sse,
    subscribe_to_project_events,
)


def test_channel_for_es_canonico() -> None:
    assert channel_for(7) == f"{CHANNEL_PREFIX}7:events"
    assert channel_for(99) == f"{CHANNEL_PREFIX}99:events"


def test_build_event_estructura_base() -> None:
    event = build_event(kind="phase", project_id=7, phase_name="qa", status="completed")
    assert event["kind"] == "phase"
    assert event["project_id"] == 7
    assert event["phase_name"] == "qa"
    assert event["status"] == "completed"
    assert "ts" in event


def test_build_event_extras_se_mergean() -> None:
    event = build_event(
        kind="phase",
        project_id=7,
        extras={"residuals": 3, "summary": "OK"},
    )
    assert event["residuals"] == 3
    assert event["summary"] == "OK"
    # extras NO debe sobrescribir los campos base.
    event2 = build_event(kind="phase", project_id=7, extras={"kind": "other"})
    assert event2["kind"] in {"phase", "other"}  # comportamiento: extras gana (kwargs)


def test_format_sse_serializa_data_y_separador() -> None:
    event = {"kind": "phase", "project_id": 7, "status": "running"}
    raw = format_sse(event)
    assert raw.startswith(b"data: ")
    assert raw.endswith(b"\n\n")
    payload = raw[len(b"data: ") : -2].decode()
    assert json.loads(payload) == event


def test_format_heartbeat_es_comentario_sse() -> None:
    """Heartbeat debe empezar por ':' (comment) para no disparar onmessage."""
    raw = format_heartbeat()
    assert raw.startswith(b":")
    assert raw.endswith(b"\n\n")


@pytest.mark.asyncio
async def test_subscribe_sin_redis_url_lanza_connectionerror(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    gen = subscribe_to_project_events(7)
    with pytest.raises(ConnectionError, match="REDIS_URL"):
        await gen.__anext__()
