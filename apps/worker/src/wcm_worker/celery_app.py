"""App Celery del worker.

Comparte la misma config que `wcm_api.tasks.celery_app`, pero aquí
**incluye** los módulos de tasks para que se registren al arrancar el
worker. El API solo encola; el worker ejecuta.

Beat schedule (Fase 10):
- `wcm.maintenance.retention_sweep` 1×/día a las 03:30 Europe/Madrid.

Observabilidad (Fase 11):
- Logging estructurado configurado al arrancar el worker.
- Sentry initialized vía SENTRY_DSN_WORKER (perezoso si vacío).
- Métricas Prometheus instrumentadas via signals
  (task_prerun/postrun/failure).
"""

from __future__ import annotations

import os
import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    worker_process_init,
)

from wcm_worker.observability import (
    CELERY_TASK_DURATION,
    CELERY_TASK_TOTAL,
    configure_logging,
    init_sentry,
)


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
            "wcm_worker.tasks.outreach",
            "wcm_worker.tasks.outreach_send",
            "wcm_worker.tasks.maintenance",
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
        task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower()
        in ("1", "true", "yes"),
        task_eager_propagates=True,
        beat_schedule={
            "retention-sweep-daily": {
                "task": "wcm.maintenance.retention_sweep",
                "schedule": crontab(hour=3, minute=30),
            },
        },
    )
    return app


celery_app: Celery = _build_celery()


# ---------- Observabilidad: bootstrapping y signals ----------

@worker_process_init.connect
def _setup_observability(*args: object, **kwargs: object) -> None:
    """Se ejecuta una vez por worker child al arrancar.

    En eager mode (tests) este signal no dispara — por eso también se
    invoca al importar el módulo (idempotente).
    """
    configure_logging(
        level=os.environ.get("LOG_LEVEL", "info"),
        env=os.environ.get("SENTRY_ENVIRONMENT", "development"),
    )
    init_sentry(
        dsn=os.environ.get("SENTRY_DSN_WORKER"),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
    )


# Llamada eager para tests y para el proceso principal (beat).
_setup_observability()


_TASK_STARTS: dict[str, float] = {}


@task_prerun.connect
def _on_task_prerun(sender=None, task_id=None, **kwargs: object) -> None:
    if task_id:
        _TASK_STARTS[task_id] = time.perf_counter()


@task_postrun.connect
def _on_task_postrun(
    sender=None, task_id=None, state=None, **kwargs: object
) -> None:
    task_name = getattr(sender, "name", "unknown") if sender else "unknown"
    start = _TASK_STARTS.pop(task_id, None) if task_id else None
    if start is not None:
        CELERY_TASK_DURATION.labels(task=task_name).observe(time.perf_counter() - start)
    status = "success" if state == "SUCCESS" else "failure"
    CELERY_TASK_TOTAL.labels(task=task_name, status=status).inc()


@task_failure.connect
def _on_task_failure(sender=None, task_id=None, **kwargs: object) -> None:
    # `task_postrun` también dispara en failure, pero state='FAILURE'.
    # Este signal nos da el exc_info; lo registramos en logs pero el
    # counter lo lleva ya `_on_task_postrun`.
    pass
