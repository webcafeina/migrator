"""Routers FastAPI. Cada uno se monta con prefijo en main."""

from wcm_api.routers import (
    audit,
    auth,
    campaigns,
    email_layout,
    health,
    leads,
    opt_out,
    outreach,
    projects,
    residual_tasks,
    system,
    templates,
    users,
    webhooks,
)
from wcm_api.routers import (
    errors as errors_router,
)

__all__ = [
    "audit",
    "auth",
    "campaigns",
    "email_layout",
    "errors_router",
    "health",
    "leads",
    "opt_out",
    "outreach",
    "projects",
    "residual_tasks",
    "system",
    "templates",
    "users",
    "webhooks",
]
