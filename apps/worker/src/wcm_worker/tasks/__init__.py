"""Tasks Celery. Cada módulo registra sus tasks con name= que matchea el
`send_task` correspondiente del API (`apps/api/src/wcm_api/tasks/enqueue.py`).
"""

# Import side-effect: registra las tasks en celery_app
from wcm_worker.tasks import clickup, fingerprinter, orchestrator, prospector  # noqa: F401
