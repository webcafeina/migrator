"""Publicación de eventos del pipeline a Redis (v0.19.0).

El orchestrator llama `publish_phase_event(project_id, phase_name, status)`
tras cada `_mark_phase`. El payload viaja por el canal
`wcm:project:{id}:events` al que la API se suscribe para el SSE
(`apps/api/src/wcm_api/services/events.py`).

Diseño:
- **Sync** (Celery worker es sync): usa `redis.Redis` síncrono.
- **Tolerante a fallos**: si Redis no responde, log warning y sigue.
  El pipeline NO debe romper porque el SSE no esté disponible.
- **Mismo formato** que el helper async del API (mismo CHANNEL_PREFIX,
  misma estructura de evento) para que el cliente reciba payloads
  consistentes.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("wcm.worker.events")

CHANNEL_PREFIX = "wcm:project:"


def channel_for(project_id: int) -> str:
    return f"{CHANNEL_PREFIX}{project_id}:events"


def publish_phase_event(
    project_id: int,
    phase_name: str,
    status: str,
    *,
    summary: str = "",
    extras: dict[str, Any] | None = None,
) -> None:
    """Publica un evento de cambio de fase. Silencioso si Redis falla.

    NUNCA propaga excepciones — el pipeline no puede romper porque el
    canal SSE no esté disponible.
    """
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return
    payload = {
        "kind": "phase",
        "project_id": project_id,
        "phase_name": phase_name,
        "status": status,
        "summary": summary[:200] if summary else "",
        "ts": datetime.now(UTC).isoformat(),
        **(extras or {}),
    }
    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_timeout=2.0)
        try:
            client.publish(channel_for(project_id), json.dumps(payload, default=str))
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001 — never fail the pipeline
        log.warning(
            "publish_phase_event_failed",
            extra={
                "project_id": project_id,
                "phase_name": phase_name,
                "error": f"{type(e).__name__}: {e}",
            },
        )
