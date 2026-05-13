"""Observabilidad de la API: logging estructurado, Sentry, Logtail, métricas.

Cada submódulo es **perezoso**: sin la env var correspondiente, no hace
nada (no init de Sentry, no handler Logtail, etc.). Esto permite levantar
la API en dev sin ninguna de las credenciales externas.
"""

from wcm_api.observability.logging_config import configure_logging
from wcm_api.observability.logtail import setup_logtail_handler
from wcm_api.observability.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    PrometheusMiddleware,
    metrics_endpoint,
)
from wcm_api.observability.sentry import init_sentry

__all__ = [
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION",
    "PrometheusMiddleware",
    "configure_logging",
    "init_sentry",
    "metrics_endpoint",
    "setup_logtail_handler",
]
