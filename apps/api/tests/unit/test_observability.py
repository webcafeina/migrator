"""Tests del módulo observability (API): logging, sentry, logtail, metrics."""

from __future__ import annotations

import json
import logging

import pytest

from wcm_api.observability.logging_config import configure_logging, reset_logging
from wcm_api.observability.logtail import reset_logtail, setup_logtail_handler
from wcm_api.observability.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    metrics_endpoint,
)
from wcm_api.observability.sentry import init_sentry, reset_sentry


@pytest.fixture(autouse=True)
def _reset_observability_state():
    reset_logging()
    reset_sentry()
    reset_logtail()
    yield
    reset_logging()
    reset_sentry()
    reset_logtail()


# ---------- configure_logging ----------

def test_configure_logging_dev_uses_console_renderer(capsys) -> None:
    configure_logging(level="info", env="development")
    logger = logging.getLogger("wcm.test")
    logger.info("hello dev")
    captured = capsys.readouterr()
    assert "hello dev" in captured.out
    # ConsoleRenderer no usa JSON: no debería empezar con `{` la línea principal.
    assert not captured.out.strip().startswith("{")


def test_configure_logging_prod_emits_json(capsys) -> None:
    configure_logging(level="info", env="production")
    logger = logging.getLogger("wcm.test.json")
    logger.info("prod_event", extra={"k": "v"})
    output = capsys.readouterr().out.strip().splitlines()
    # La última línea es la nuestra (puede haber otras de setup).
    last = output[-1]
    payload = json.loads(last)
    assert payload["event"] == "prod_event"
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_configure_logging_is_idempotent(capsys) -> None:
    configure_logging(level="info", env="development")
    configure_logging(level="debug", env="development")  # no-op
    # Solo debe haber 1 handler en root (no duplicado por segunda llamada).
    assert len(logging.getLogger().handlers) == 1


def test_configure_logging_silences_noisy_libs() -> None:
    configure_logging(level="debug", env="development")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("botocore").level == logging.WARNING


# ---------- init_sentry ----------

def test_init_sentry_returns_false_without_dsn() -> None:
    assert init_sentry(dsn=None) is False
    assert init_sentry(dsn="") is False


def test_init_sentry_returns_true_with_fake_dsn() -> None:
    # Sentry acepta el DSN sin contactar el server; basta para que init devuelva True.
    result = init_sentry(
        dsn="https://abc@sentry.example.com/1",
        environment="test",
        traces_sample_rate=0.0,
        component="api-test",
    )
    assert result is True


def test_init_sentry_is_idempotent() -> None:
    init_sentry(dsn="https://abc@sentry.example.com/1")
    # Segunda llamada con DSN distinto: igualmente no-op (devuelve True).
    assert init_sentry(dsn="https://other@sentry.example.com/2") is True


# ---------- setup_logtail_handler ----------

def test_logtail_handler_skipped_without_token() -> None:
    configure_logging(level="info", env="development")
    n_before = len(logging.getLogger().handlers)
    assert setup_logtail_handler(source_token=None) is False
    assert len(logging.getLogger().handlers) == n_before


def test_logtail_handler_attached_with_token() -> None:
    configure_logging(level="info", env="development")
    n_before = len(logging.getLogger().handlers)
    result = setup_logtail_handler(source_token="fake-token-not-real")
    assert result is True
    assert len(logging.getLogger().handlers) == n_before + 1


# ---------- metrics ----------

def test_http_requests_counter_increments() -> None:
    before = HTTP_REQUESTS_TOTAL.labels(method="GET", path="/foo", status="200")._value.get()
    HTTP_REQUESTS_TOTAL.labels(method="GET", path="/foo", status="200").inc()
    after = HTTP_REQUESTS_TOTAL.labels(method="GET", path="/foo", status="200")._value.get()
    assert after == before + 1


def test_http_duration_histogram_observes() -> None:
    HTTP_REQUEST_DURATION.labels(method="GET", path="/foo").observe(0.123)
    # Sin assertion sobre el output: histogram interno acepta sin error.


def test_metrics_endpoint_returns_prometheus_format() -> None:
    HTTP_REQUESTS_TOTAL.labels(method="POST", path="/api/v1/leads", status="201").inc()
    resp = metrics_endpoint()
    assert resp.status_code == 200
    body = resp.body.decode("utf-8") if isinstance(resp.body, bytes) else resp.body
    assert "wcm_http_requests_total" in body
    assert "wcm_http_request_duration_seconds" in body
