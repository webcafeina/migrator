"""Punto de entrada FastAPI. Construye la app y monta los routers.

`uvicorn wcm_api.main:app` para producción.
`create_app()` se usa en tests con `httpx.AsyncClient(app=create_app())`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wcm_api.config import ApiSettings, get_settings
from wcm_api.errors import register_error_handlers
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
    # Aquí en futuras fases: inicializar Sentry, structlog, etc.
    # En Fase 5 lo dejamos limpio. Fase 11 lo amplía.
    yield


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    s = settings or get_settings()

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

    register_error_handlers(app)

    # Health/probes — sin prefijo de versión
    app.include_router(health.router)

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
