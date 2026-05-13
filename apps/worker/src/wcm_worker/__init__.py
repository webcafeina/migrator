"""Webcafeína Migrator — Celery worker.

Arranca con:
    celery -A wcm_worker.celery_app worker --loglevel=info --concurrency=4

Las tasks viven en `wcm_worker.tasks.*` y se autocargan al construir la app.
"""

from wcm_worker.celery_app import celery_app
# Import explícito de las tasks para garantizar registro al importar wcm_worker
# directamente (no solo cuando Celery worker invoca via include=[...]).
from wcm_worker import tasks  # noqa: F401

__all__ = ["celery_app"]
