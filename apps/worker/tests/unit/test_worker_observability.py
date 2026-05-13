"""Tests del módulo observability del worker."""

from __future__ import annotations

import logging

import pytest

from wcm_worker.observability.logging_config import configure_logging, reset_logging
from wcm_worker.observability.metrics import (
    AGENT_RUN_TOTAL,
    REGISTRY,
    observe_agent,
    observe_celery_task,
)
from wcm_worker.observability.sentry import init_sentry, reset_sentry


@pytest.fixture(autouse=True)
def _reset():
    reset_logging()
    reset_sentry()
    yield
    reset_logging()
    reset_sentry()


def test_logging_config_idempotent() -> None:
    configure_logging(env="development")
    configure_logging(env="development")
    assert len(logging.getLogger().handlers) == 1


def test_init_sentry_skipped_without_dsn() -> None:
    assert init_sentry(dsn=None) is False


def test_observe_agent_records_success() -> None:
    before = AGENT_RUN_TOTAL.labels(agent="prospector", status="success")._value.get()
    with observe_agent("prospector"):
        pass
    after = AGENT_RUN_TOTAL.labels(agent="prospector", status="success")._value.get()
    assert after == before + 1


def test_observe_agent_records_failure() -> None:
    before = AGENT_RUN_TOTAL.labels(agent="enricher", status="failure")._value.get()
    with pytest.raises(RuntimeError):
        with observe_agent("enricher"):
            raise RuntimeError("boom")
    after = AGENT_RUN_TOTAL.labels(agent="enricher", status="failure")._value.get()
    assert after == before + 1


def test_observe_celery_task_failure_increments_counter() -> None:
    from wcm_worker.observability.metrics import CELERY_TASK_TOTAL

    before = CELERY_TASK_TOTAL.labels(task="wcm.test", status="failure")._value.get()
    with pytest.raises(ValueError):
        with observe_celery_task("wcm.test"):
            raise ValueError("nope")
    after = CELERY_TASK_TOTAL.labels(task="wcm.test", status="failure")._value.get()
    assert after == before + 1


def test_metrics_registry_has_no_default_metrics_pollution() -> None:
    """El registry propio no debe arrastrar métricas del global default."""
    # `python_gc_objects_collected` es una métrica default del registry global.
    from prometheus_client import generate_latest

    body = generate_latest(REGISTRY).decode()
    assert "python_gc_objects_collected" not in body
    assert "wcm_celery_tasks_total" in body
