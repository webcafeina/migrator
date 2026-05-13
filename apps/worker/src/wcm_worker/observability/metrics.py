"""Métricas Prometheus del worker.

Las exponemos vía `multiprocess_dir` para que Celery (multi-worker) las
agregue correctamente. Para mantenerlo sencillo en MVP, usamos un registry
single-process; en Fase 12 cuando haya N workers reales, migrar a
`MultiProcessCollector` (1 línea de cambio).

Helpers:
- `observe_task(name)`: decorator de Celery task que mide duración + count.
- `observe_agent(name)`: contexto para subagentes.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from collections.abc import Iterator

from prometheus_client import CollectorRegistry, Counter, Histogram

REGISTRY = CollectorRegistry()

CELERY_TASK_TOTAL = Counter(
    "wcm_celery_tasks_total",
    "Total Celery tasks ejecutadas en el worker",
    labelnames=("task", "status"),  # status: success | failure
    registry=REGISTRY,
)

CELERY_TASK_DURATION = Histogram(
    "wcm_celery_task_duration_seconds",
    "Latencia de Celery tasks",
    labelnames=("task",),
    buckets=(0.05, 0.25, 1.0, 5.0, 15.0, 60.0, 300.0, 1800.0),
    registry=REGISTRY,
)

AGENT_RUN_TOTAL = Counter(
    "wcm_agent_runs_total",
    "Ejecuciones de subagentes (BaseAgent.run)",
    labelnames=("agent", "status"),
    registry=REGISTRY,
)

AGENT_RUN_DURATION = Histogram(
    "wcm_agent_run_duration_seconds",
    "Latencia por ejecución de subagente",
    labelnames=("agent",),
    buckets=(0.1, 0.5, 2.0, 10.0, 60.0, 300.0),
    registry=REGISTRY,
)


@contextmanager
def observe_agent(name: str) -> Iterator[None]:
    """Mide duración y cuenta éxito/fallo de la ejecución de un subagente."""
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "failure"
        raise
    finally:
        AGENT_RUN_DURATION.labels(agent=name).observe(time.perf_counter() - start)
        AGENT_RUN_TOTAL.labels(agent=name, status=status).inc()


@contextmanager
def observe_celery_task(name: str) -> Iterator[None]:
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "failure"
        raise
    finally:
        CELERY_TASK_DURATION.labels(task=name).observe(time.perf_counter() - start)
        CELERY_TASK_TOTAL.labels(task=name, status=status).inc()
