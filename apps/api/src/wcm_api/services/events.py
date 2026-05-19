"""Server-Sent Events (SSE) sobre Redis pub/sub para reactividad sub-segundo (v0.19.0).

Patrón:
- El worker publica al canal `wcm:project:{id}:events` cada vez que cambia
  una fase (start, success, fail, skip).
- El endpoint `GET /api/v1/projects/{id}/events` se suscribe a ese canal
  y stream-ea los mensajes al navegador como `text/event-stream`.
- El cliente (EventSource) llama `router.refresh()` en cada mensaje para
  re-fetchar el Server Component.

Reuso de la conexión Redis ya configurada (`REDIS_URL` en `.env`).
Si Redis no está disponible al abrir el stream → el endpoint responde 503
y el cliente cae al polling 2s tradicional (ProjectPoller).

Formato de mensaje (JSON serializado en data:):
    {
        "kind": "phase",
        "project_id": 7,
        "phase_name": "deploy_wp",
        "status": "completed",
        "ts": "2026-05-19T12:00:00Z"
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("wcm.api.events")

CHANNEL_PREFIX = "wcm:project:"
# Heartbeat cada 25s para que proxies (nginx) no corten la conexión idle.
_HEARTBEAT_INTERVAL_S = 25.0


def channel_for(project_id: int) -> str:
    """Nombre canónico del canal Redis para un proyecto."""
    return f"{CHANNEL_PREFIX}{project_id}:events"


def build_event(
    *,
    kind: str,
    project_id: int,
    phase_name: str | None = None,
    status: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estructura canónica del payload emitido al canal Redis."""
    return {
        "kind": kind,
        "project_id": project_id,
        "phase_name": phase_name,
        "status": status,
        "ts": datetime.now(UTC).isoformat(),
        **(extras or {}),
    }


def format_sse(event: dict[str, Any]) -> bytes:
    """Serializa un evento al wire-format SSE (`data: <json>\\n\\n`)."""
    return f"data: {json.dumps(event, default=str)}\n\n".encode()


def format_heartbeat() -> bytes:
    """Comentario SSE que mantiene la conexión viva sin disparar onmessage."""
    return b": heartbeat\n\n"


async def subscribe_to_project_events(project_id: int) -> AsyncIterator[bytes]:
    """Async generator que stream-ea eventos SSE para un proyecto.

    Si Redis no responde, propaga `ConnectionError` para que el endpoint
    devuelva 503 (cliente cae a polling). El generator itera hasta que
    el cliente cierra la conexión (StreamingResponse maneja la cancelación).
    """
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        raise ConnectionError("REDIS_URL no configurado")

    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url, decode_responses=False)
    pubsub = redis.pubsub()
    channel = channel_for(project_id)
    try:
        await pubsub.subscribe(channel)
        # Mensaje inicial confirmando la suscripción (útil en debug + el
        # cliente lo descarta porque kind=hello).
        yield format_sse(
            build_event(kind="hello", project_id=project_id, status="subscribed")
        )

        last_heartbeat = asyncio.get_event_loop().time()
        while True:
            # get_message con timeout pequeño para combinar lectura + heartbeat.
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            now = asyncio.get_event_loop().time()
            if msg and msg.get("type") == "message":
                raw = msg.get("data") or b""
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    event = build_event(
                        kind="raw", project_id=project_id, extras={"raw": raw[:200]}
                    )
                yield format_sse(event)
                last_heartbeat = now
            elif now - last_heartbeat >= _HEARTBEAT_INTERVAL_S:
                yield format_heartbeat()
                last_heartbeat = now
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 — cleanup, no debe propagar
            pass
        try:
            await redis.aclose()
        except Exception:  # noqa: BLE001
            pass
