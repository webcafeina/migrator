"""App Celery del worker.

Comparte la misma config que `wcm_api.tasks.celery_app`, pero aquí
**incluye** los módulos de tasks para que se registren al arrancar el
worker. El API solo encola; el worker ejecuta.
"""

from __future__ import annotations

import os
from celery import Celery


def _build_celery() -> Celery:
    broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    app = Celery(
        "wcm",
        broker=broker,
        backend=backend,
        include=[
            "wcm_worker.tasks.orchestrator",
            "wcm_worker.tasks.prospector",
            "wcm_worker.tasks.fingerprinter",
            "wcm_worker.tasks.clickup",
        ],
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
        # En tests, eager mode evita necesitar broker real:
        task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower()
        in ("1", "true", "yes"),
        task_eager_propagates=True,
    )
    return app


celery_app: Celery = _build_celery()
