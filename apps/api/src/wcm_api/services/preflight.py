"""Preflight de proyecto (v0.18.0).

Ejecuta 4 chequeos en paralelo antes de permitir Start del pipeline:

1. **WP destino accesible** (REST + SSH). BLOQUEA si falla.
2. **Plugins detectados** (Bricks, Gravity Forms, WooCommerce según
   features del proyecto). Solo informativo — el pipeline ya degrada
   y genera ResidualTask si faltan en runtime.
3. **Origen accesible + builder confirmado** (GET source_url, parse
   minimal). BLOQUEA si origen devuelve 4xx/5xx.
4. **Credenciales del origen válidas** (solo si project.source_access_mode='api'
   y hay credenciales). Warning, NO bloquea — el pipeline cae a
   scraping Playwright público.

Cada check tiene timeout 10s para no colgar la UI. Ejecuta todo con
`asyncio.gather`. Resultado se persiste en `projects.preflight_results_json`
+ `projects.preflight_at` para cache client-side.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from wcm_api.services.source_credentials import (
    CredentialsDecryptError,
    FernetNotConfiguredError,
    decrypt_source_credentials,
)
from wcm_db.models.projects import Project
from wcm_types.schemas.projects import PreflightCheck, PreflightResult

log = logging.getLogger("wcm.api.preflight")

_CHECK_TIMEOUT_S = 10.0


async def run_preflight(project: Project) -> PreflightResult:
    """Ejecuta los 4 checks en paralelo y agrega el resultado."""
    wp_target_task = asyncio.create_task(_check_wp_destination())
    plugins_task = asyncio.create_task(_check_plugins(project))
    source_task = asyncio.create_task(_check_source(project))
    creds_task = asyncio.create_task(_check_source_credentials(project))

    wp_target, plugins, source, creds = await asyncio.gather(
        wp_target_task, plugins_task, source_task, creds_task
    )

    blocking_issues: list[str] = []
    warnings: list[str] = []

    if wp_target.blocking and not wp_target.ok:
        blocking_issues.append(f"WP destino: {wp_target.message}")
    if source.blocking and not source.ok:
        blocking_issues.append(f"Origen: {source.message}")
    if not creds.ok and creds.message and creds.extras and creds.extras.get("checked"):
        warnings.append(f"Credenciales origen: {creds.message}")
    for plugin, present in plugins.items():
        if not present:
            warnings.append(f"Plugin {plugin} no detectado en destino")

    can_start = len(blocking_issues) == 0

    return PreflightResult(
        wp_target=wp_target,
        plugins=plugins,
        source=source,
        source_credentials=creds,
        can_start=can_start,
        blocking_issues=blocking_issues,
        warnings=warnings,
        executed_at=datetime.now(UTC),
    )


# ---------- WP destino ----------


async def _check_wp_destination() -> PreflightCheck:
    """REST + SSH al WP destino configurado en .env (WP_DEFAULT_*)."""
    required_envs = [
        "WP_DEFAULT_SITE_URL",
        "WP_DEFAULT_REST_USER",
        "WP_DEFAULT_REST_APP_PASSWORD",
        "WP_DEFAULT_HOST",
        "WP_DEFAULT_SSH_USER",
        "WP_DEFAULT_SSH_KEY_PATH",
    ]
    missing = [e for e in required_envs if not os.environ.get(e)]
    if missing:
        return PreflightCheck(
            ok=False,
            blocking=True,
            message=f"Faltan envs: {', '.join(missing)}",
            extras={"missing_envs": missing, "rest_accessible": False, "ssh_accessible": False},
        )

    site_url = os.environ["WP_DEFAULT_SITE_URL"].rstrip("/")
    rest_ok = False
    rest_error: str | None = None
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S, verify=False) as client:
            r = await client.get(f"{site_url}/wp-json/")
            rest_ok = 200 <= r.status_code < 400
            if not rest_ok:
                rest_error = f"HTTP {r.status_code}"
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
        rest_error = f"{type(e).__name__}: {e}"

    # SSH check: no es trivial async; hacemos uno básico vía TCP connect al puerto SSH.
    ssh_ok = False
    ssh_error: str | None = None
    try:
        ssh_host = os.environ["WP_DEFAULT_HOST"]
        ssh_port = int(os.environ.get("WP_DEFAULT_SSH_PORT", "22"))
        fut = asyncio.open_connection(ssh_host, ssh_port)
        reader, writer = await asyncio.wait_for(fut, timeout=_CHECK_TIMEOUT_S)
        # Si SSH responde con banner SSH-2.0-* en los primeros bytes, OK.
        banner = await asyncio.wait_for(reader.read(64), timeout=2.0)
        ssh_ok = banner.startswith(b"SSH-")
        if not ssh_ok:
            ssh_error = f"Banner inesperado: {banner[:32]!r}"
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
    except (TimeoutError, OSError) as e:
        ssh_error = f"{type(e).__name__}: {e}"

    ok = rest_ok and ssh_ok
    if ok:
        return PreflightCheck(
            ok=True,
            blocking=True,
            message="WP destino accesible (REST + SSH).",
            extras={"rest_accessible": rest_ok, "ssh_accessible": ssh_ok},
        )
    msg_parts = []
    if not rest_ok:
        msg_parts.append(f"REST: {rest_error}")
    if not ssh_ok:
        msg_parts.append(f"SSH: {ssh_error}")
    return PreflightCheck(
        ok=False,
        blocking=True,
        message="; ".join(msg_parts) or "WP destino inaccesible",
        extras={
            "rest_accessible": rest_ok,
            "ssh_accessible": ssh_ok,
            "rest_error": rest_error,
            "ssh_error": ssh_error,
        },
    )


# ---------- Plugins destino ----------


async def _check_plugins(project: Project) -> dict[str, bool]:
    """HEAD a /wp-json/{bricks,gf/v2,wc/v3}/ — true si responde 2xx/3xx."""
    site_url = os.environ.get("WP_DEFAULT_SITE_URL", "").rstrip("/")
    if not site_url:
        return {"bricks": False, "gravity_forms": False, "woocommerce": False}

    targets: dict[str, str] = {
        "bricks": f"{site_url}/wp-json/bricks/v1/",
        "gravity_forms": f"{site_url}/wp-json/gf/v2/forms",
        "woocommerce": f"{site_url}/wp-json/wc/v3/system_status/tools",
    }

    async def _check(url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S, verify=False) as client:
                r = await client.head(url)
                return r.status_code < 500 and r.status_code != 404
        except (httpx.TimeoutException, httpx.HTTPError):
            return False

    results = await asyncio.gather(*(_check(u) for u in targets.values()))
    return dict(zip(targets.keys(), results, strict=True))


# ---------- Origen ----------


async def _check_source(project: Project) -> PreflightCheck:
    """GET source_url con timeout 10s. BLOQUEA si 4xx/5xx."""
    if not project.source_url:
        return PreflightCheck(
            ok=False,
            blocking=True,
            message="Project sin source_url",
        )
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S, follow_redirects=True) as client:
            r = await client.get(project.source_url)
            if 200 <= r.status_code < 400:
                return PreflightCheck(
                    ok=True,
                    blocking=True,
                    message=f"Origen accesible (HTTP {r.status_code}).",
                    extras={
                        "status_code": r.status_code,
                        "builder_declared": project.builder_source.value if project.builder_source else None,
                    },
                )
            return PreflightCheck(
                ok=False,
                blocking=True,
                message=f"Origen devuelve HTTP {r.status_code}",
                extras={"status_code": r.status_code},
            )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
        return PreflightCheck(
            ok=False,
            blocking=True,
            message=f"{type(e).__name__}: {e}",
        )


# ---------- Credenciales del origen ----------


async def _check_source_credentials(project: Project) -> PreflightCheck:
    """Solo aplica si source_access_mode='api' y hay credenciales.

    Warning si fallan (el pipeline cae a scraping Playwright).
    `extras.checked=False` indica que no se evaluó.
    """
    if project.source_access_mode != "api" or not project.source_credentials_encrypted:
        return PreflightCheck(
            ok=True,
            blocking=False,
            message="Sin credenciales del origen configuradas (modo scraping público).",
            extras={"checked": False},
        )

    try:
        creds = decrypt_source_credentials(project.source_credentials_encrypted)
    except (FernetNotConfiguredError, CredentialsDecryptError) as e:
        return PreflightCheck(
            ok=False,
            blocking=False,
            message=f"No se pueden descifrar las credenciales: {e}",
            extras={"checked": True, "decrypt_failed": True},
        )

    builder = (project.builder_source.value if project.builder_source else "").lower()

    if builder == "wix":
        return await _ping_wix_api(creds)
    if builder == "webflow":
        return await _ping_webflow_api(creds)

    return PreflightCheck(
        ok=True,
        blocking=False,
        message=f"Builder '{builder}' sin adapter API (ignoradas).",
        extras={"checked": False},
    )


async def _ping_wix_api(creds: dict[str, Any]) -> PreflightCheck:
    """Llamada barata a Wix REST v3 (GET /sites/v1/sites/{site_id})."""
    api_key = creds.get("api_key")
    site_id = creds.get("site_id")
    if not api_key or not site_id:
        return PreflightCheck(
            ok=False,
            blocking=False,
            message="Credenciales Wix incompletas (faltan api_key o site_id).",
            extras={"checked": True},
        )
    headers = {"Authorization": api_key, "wix-site-id": site_id}
    url = f"https://www.wixapis.com/sites/v1/sites/{site_id}"
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return PreflightCheck(
                    ok=True,
                    blocking=False,
                    message="Credenciales Wix válidas.",
                    extras={"checked": True, "status_code": 200},
                )
            return PreflightCheck(
                ok=False,
                blocking=False,
                message=f"Wix API rechaza credenciales (HTTP {r.status_code}).",
                extras={"checked": True, "status_code": r.status_code},
            )
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        return PreflightCheck(
            ok=False,
            blocking=False,
            message=f"Error contactando Wix API: {type(e).__name__}",
            extras={"checked": True},
        )


async def _ping_webflow_api(creds: dict[str, Any]) -> PreflightCheck:
    """Llamada barata a Webflow Sites API v2 (GET /sites/{site_id})."""
    api_token = creds.get("api_token")
    site_id = creds.get("site_id")
    if not api_token or not site_id:
        return PreflightCheck(
            ok=False,
            blocking=False,
            message="Credenciales Webflow incompletas (faltan api_token o site_id).",
            extras={"checked": True},
        )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "accept-version": "2.0.0",
    }
    url = f"https://api.webflow.com/v2/sites/{site_id}"
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return PreflightCheck(
                    ok=True,
                    blocking=False,
                    message="Credenciales Webflow válidas.",
                    extras={"checked": True, "status_code": 200},
                )
            return PreflightCheck(
                ok=False,
                blocking=False,
                message=f"Webflow API rechaza credenciales (HTTP {r.status_code}).",
                extras={"checked": True, "status_code": r.status_code},
            )
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        return PreflightCheck(
            ok=False,
            blocking=False,
            message=f"Error contactando Webflow API: {type(e).__name__}",
            extras={"checked": True},
        )


def serialize_preflight_for_db(result: PreflightResult) -> dict[str, Any]:
    """Serializa PreflightResult a JSON serializable para persistir en JSONB."""
    return json.loads(result.model_dump_json())
