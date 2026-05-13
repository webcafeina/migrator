"""Routers FastAPI. Cada uno se monta con prefijo en main."""

from wcm_api.routers import (
    auth,
    campaigns,
    errors as errors_router,
    health,
    leads,
    opt_out,
    projects,
    residual_tasks,
    users,
    webhooks,
)

__all__ = [
    "auth",
    "campaigns",
    "errors_router",
    "health",
    "leads",
    "opt_out",
    "projects",
    "residual_tasks",
    "users",
    "webhooks",
]
