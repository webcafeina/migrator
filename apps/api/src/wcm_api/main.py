"""Punto de entrada FastAPI. Construye la app y monta los routers.

`uvicorn wcm_api.main:app` para producción.
`create_app()` se usa en tests con `httpx.AsyncClient(app=create_app())`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wcm_api.config import ApiSettings, get_settings
from wcm_api.errors import register_error_handlers
from wcm_api.observability import (
    PrometheusMiddleware,
    configure_logging,
    init_sentry,
    metrics_endpoint,
    setup_logtail_handler,
)
from wcm_api.routers import (
    auth,
    campaigns,
    errors_router,
    health,
    leads,
    opt_out,
    outreach,
    projects,
    residual_tasks,
    users,
    webhooks,
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    s = settings or get_settings()

    # Observabilidad. Idempotente — segundas llamadas son no-op.
    configure_logging(level=s.log_level, env=s.env)
    init_sentry(
        dsn=s.sentry_dsn_api,
        environment=s.sentry_environment,
        traces_sample_rate=s.sentry_traces_sample_rate,
        component="api",
    )
    setup_logtail_handler(source_token=s.logtail_source_token, level=s.log_level)

    app = FastAPI(
        title="Webcafeína Migrator API",
        version="0.1.0",
        description=(
            "API interna de Webcafeína para prospección comercial y "
            "migración de webs Wix/Hostinger/Webflow a WordPress + Bricks."
        ),
        lifespan=_lifespan,
        docs_url="/docs" if not s.is_production else None,
        redoc_url="/redoc" if not s.is_production else None,
        openapi_url="/openapi.json" if not s.is_production else None,
    )

    # CORS — solo orígenes whitelisted (dashboard Next).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    # Prometheus: añadimos después de CORS para no contar preflight OPTIONS
    # cancelados antes de llegar a los routers.
    app.add_middleware(PrometheusMiddleware)

    register_error_handlers(app)

    # Health/probes y /metrics — sin prefijo de versión, sin auth.
    app.include_router(health.router)
    app.add_api_route(
        "/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False,
    )

    # Opt-out RGPD — sin prefijo (URL humana, no API JSON)
    app.include_router(opt_out.router)

    # API v1
    v1_prefix = "/api/v1"
    app.include_router(auth.router, prefix=v1_prefix)
    app.include_router(users.router, prefix=v1_prefix)
    app.include_router(leads.router, prefix=v1_prefix)
    app.include_router(campaigns.router, prefix=v1_prefix)
    app.include_router(outreach.router, prefix=v1_prefix)
    app.include_router(projects.router, prefix=v1_prefix)
    app.include_router(residual_tasks.router, prefix=v1_prefix)
    app.include_router(errors_router.router, prefix=v1_prefix)
    app.include_router(webhooks.router, prefix=v1_prefix)

    return app


# Para `uvicorn wcm_api.main:app`
app = create_app()
