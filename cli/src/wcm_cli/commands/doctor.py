"""Comando `wcm doctor` — diagnóstico del entorno.

Comprueba en orden:
1. `.env` existe y tiene las vars críticas.
2. API responde a `/health`.
3. DB Postgres sync responde a `SELECT 1`.
4. Redis ping (broker Celery).
5. Sandbox WP destino responde a /wp-json (si configurado).

No corrige nada, solo reporta. Útil tras `git pull`, `pip install`, etc.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import httpx
import typer

from wcm_cli import output
from wcm_cli.config import CliConfig

app = typer.Typer(help="Diagnóstico del entorno")


_REQUIRED_ENV_KEYS = (
    "ENV",
    "SECRET_KEY",
    "JWT_SECRET",
    "DATABASE_URL",
    "DATABASE_SYNC_URL",
    "API_URL",
)

_OPTIONAL_ENV_KEYS = (
    "REDIS_URL",
    "WP_DEFAULT_SITE_URL",
    "WP_DEFAULT_REST_USER",
    "WP_DEFAULT_REST_APP_PASSWORD",
    "CLICKUP_API_TOKEN",
    "RESEND_API_KEY",
    "VOYAGE_API_KEY",
)


@app.callback(invoke_without_command=True)
def doctor() -> None:
    """Diagnóstico end-to-end del entorno del operador."""
    output.header("Diagnóstico Webcafeína Migrator")

    cfg = CliConfig.load()
    results: list[tuple[str, str, str]] = []  # (check, status, detail)

    # 1) .env requerido
    for key in _REQUIRED_ENV_KEYS:
        value = os.environ.get(key)
        if not value:
            results.append((f"env:{key}", "✕", "falta o vacío"))
        else:
            results.append((f"env:{key}", "✓", "ok"))

    # 2) .env opcional (informativo)
    for key in _OPTIONAL_ENV_KEYS:
        value = os.environ.get(key)
        if not value:
            results.append((f"env:{key}", "—", "no configurado (opcional)"))
        else:
            results.append((f"env:{key}", "✓", "ok"))

    # 3) API health
    api_url = cfg.api_url
    try:
        r = httpx.get(f"{api_url}/health", timeout=5.0, verify=cfg.verify_ssl)
        if r.status_code == 200 and r.json().get("status") == "ok":
            results.append(("api:health", "✓", f"{api_url}/health → 200"))
        else:
            results.append(("api:health", "⚠", f"HTTP {r.status_code}"))
    except httpx.HTTPError as e:
        results.append(("api:health", "✕", f"unreachable: {type(e).__name__}"))

    # 4) Postgres sync via TCP probe
    db_url = os.environ.get("DATABASE_SYNC_URL", "")
    if db_url:
        parsed = urlparse(db_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        if _tcp_port_open(host, port):
            results.append(("db:postgres", "✓", f"{host}:{port} reachable"))
        else:
            results.append(("db:postgres", "✕", f"{host}:{port} cerrado"))
    else:
        results.append(("db:postgres", "—", "DATABASE_SYNC_URL no configurada"))

    # 5) Redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(redis_url)
    if _tcp_port_open(parsed.hostname or "localhost", parsed.port or 6379):
        results.append(("redis", "✓", f"{parsed.hostname}:{parsed.port or 6379} reachable"))
    else:
        results.append(("redis", "✕", f"{parsed.hostname}:{parsed.port or 6379} cerrado"))

    # 6) Sandbox WP destino
    wp_url = os.environ.get("WP_DEFAULT_SITE_URL")
    if wp_url:
        try:
            r = httpx.get(f"{wp_url.rstrip('/')}/wp-json/", timeout=5.0, verify=False)
            if r.status_code == 200:
                results.append(("wp:sandbox", "✓", f"{wp_url}/wp-json → 200"))
            else:
                results.append(("wp:sandbox", "⚠", f"HTTP {r.status_code}"))
        except httpx.HTTPError as e:
            results.append(("wp:sandbox", "✕", f"unreachable: {type(e).__name__}"))
    else:
        results.append(("wp:sandbox", "—", "WP_DEFAULT_SITE_URL no configurada"))

    # Render
    if output.is_json_mode():
        output.emit_json([
            {"check": c, "status": s, "detail": d} for c, s, d in results
        ])
    else:
        rows = [[c, s, d] for c, s, d in results]
        output.render_table("Checks", ["check", "status", "detail"], rows)
        # Resumen
        errors = sum(1 for _, s, _ in results if s == "✕")
        warns = sum(1 for _, s, _ in results if s == "⚠")
        if errors:
            output.error(f"{errors} checks fallan. Revisa los detalles arriba.")
        elif warns:
            output.warning(f"{warns} checks con avisos.")
        else:
            output.success("Todos los checks críticos OK.")

    # Exit code != 0 si hay errores críticos
    crit = [c for c, s, _ in results if s == "✕" and not c.startswith("env:") or c.startswith("env:") and c.replace("env:", "") in _REQUIRED_ENV_KEYS and s == "✕"]
    if crit:
        raise typer.Exit(code=2)


def _tcp_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False
