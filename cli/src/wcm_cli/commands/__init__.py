"""Comandos del CLI. Cada uno se registra como Typer sub-app en `main.app`."""

from wcm_cli.commands import (
    auth,
    campaigns,
    deploy,
    doctor,
    leads,
    projects,
    residual_tasks,
    setup as setup_cmd,
)

__all__ = [
    "auth",
    "campaigns",
    "deploy",
    "doctor",
    "leads",
    "projects",
    "residual_tasks",
    "setup_cmd",
]
