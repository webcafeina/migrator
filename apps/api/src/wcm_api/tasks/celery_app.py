"""App Celery compartida entre la API (que solo encola) y el worker (que ejecuta).

La API importa este módulo y llama `.send_task(name, args, kwargs)`. El
worker (apps/worker, Fase 6) define las tasks reales con el mismo nombre.
Mientras worker no esté implementado, encolar funciona — el job queda en
Redis hasta que un worker lo consuma.
"""

from __future__ import annotations

from celery import Celery

from wcm_api.config import get_settings


def _build_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "wcm",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_default_queue="webcafeina",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Europe/Madrid",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app: Celery = _build_celery()
