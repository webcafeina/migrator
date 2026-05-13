"""Métricas Prometheus para la API.

Registry custom (no usamos el default global) para evitar conflictos en
tests cuando se importan múltiples veces. Endpoint `/metrics` expone el
formato OpenMetrics estándar.

Métricas expuestas:
- `wcm_http_requests_total{method,path,status}`: Counter por request.
- `wcm_http_request_duration_seconds{method,path}`: Histogram de latencia.
- `wcm_celery_tasks_enqueued_total{task}`: tasks encoladas desde la API
  (la observación de ejecución vive en el worker, no aquí).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: Registry propio. Evita pisar el default si otro código (tests) registra
#: las mismas métricas más de una vez.
REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "wcm_http_requests_total",
    "Total de requests HTTP atendidas por la API",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION = Histogram(
    "wcm_http_request_duration_seconds",
    "Latencia de requests HTTP en segundos",
    labelnames=("method", "path"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

CELERY_TASKS_ENQUEUED = Counter(
    "wcm_celery_tasks_enqueued_total",
    "Tasks Celery encoladas desde la API",
    labelnames=("task",),
    registry=REGISTRY,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware que registra duración + counter por request.

    El `path` se toma del route template (`/projects/{id}`) si está
    resuelto, para evitar explosión de cardinalidad por IDs reales.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        start = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = _route_template(request)
            HTTP_REQUEST_DURATION.labels(
                method=request.method, path=path
            ).observe(elapsed)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status=str(status_code)
            ).inc()


def _route_template(request: Request) -> str:
    """Devuelve la plantilla de ruta resuelta o el path crudo como fallback.

    El template se resuelve solo tras pasar por el router; si llegamos al
    middleware antes, `request.scope["route"]` puede no estar todavía.
    Para minimizar cardinalidad, en ese caso truncamos a los dos primeros
    segmentos (`/api/v1`) en lugar de devolver el path completo.
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    raw = request.url.path or "/"
    segments = raw.split("/")[:4]  # ['', 'api', 'v1', 'projects']
    return "/".join(segments) or "/"


def metrics_endpoint() -> Response:
    """Devuelve el dump actual del registry en formato Prometheus."""
    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
