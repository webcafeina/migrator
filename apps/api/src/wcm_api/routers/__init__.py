"""Routers FastAPI. Cada uno se monta con prefijo en main."""

from wcm_api.routers import (
    auth,
    campaigns,
    health,
    leads,
    opt_out,
    outreach,
    projects,
    residual_tasks,
    users,
    webhooks,
)
from wcm_api.routers import (
    errors as errors_router,
)

__all__ = [
    "auth",
    "campaigns",
    "errors_router",
    "health",
    "leads",
    "opt_out",
    "outreach",
    "projects",
    "residual_tasks",
    "users",
    "webhooks",
]
