"""Cliente Python para el sidecar Node `webflow-sidecar.js`.

scraper-origin agente llama a `run_webflow_sidecar(url, ...)` que arranca el
proceso Node, lo alimenta con la URL y captura el JSON de stdout. Falla con
`WebflowSidecarError` con stderr en el mensaje si Node/Puppeteer no están
instalados o el sitio devuelve un error.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SIDECAR_PATH = Path(__file__).parent / "webflow-sidecar.js"


class WebflowSidecarError(RuntimeError):
    """Sidecar Node falló (timeout, error de red, dependencias faltantes)."""


@dataclass
class WebflowSidecarResult:
    html: str
    url: str
    ix2_state: dict[str, Any] | None
    page_timings: dict[str, int]
    warnings: list[str]


async def run_webflow_sidecar(
    url: str,
    *,
    proxy: str | None = None,
    user_agent: str | None = None,
    timeout_s: float = 35.0,
    node_bin: str | None = None,
) -> WebflowSidecarResult:
    """Ejecuta el sidecar Node y devuelve el resultado parseado.

    Requiere `node` en PATH (o pasado por `node_bin`) y Puppeteer instalado en
    `packages/scraper-core/src/wcm_scraper_core/sidecar/node_modules/`. Si no
    están, lanza `WebflowSidecarError` con mensaje accionable.
    """
    node = node_bin or shutil.which("node")
    if node is None:
        raise WebflowSidecarError(
            "Node.js no encontrado en PATH. Instala Node 20+ y vuelve a intentar."
        )
    if not SIDECAR_PATH.exists():  # pragma: no cover
        raise WebflowSidecarError(f"sidecar no encontrado en {SIDECAR_PATH}")

    cmd = [node, str(SIDECAR_PATH), f"--url={url}", f"--timeout-ms={int(timeout_s * 1000)}"]
    if proxy:
        cmd.append(f"--proxy={proxy}")
    if user_agent:
        cmd.append(f"--ua={user_agent}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(SIDECAR_PATH.parent),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_s + 5.0
        )
    except TimeoutError as e:
        process.kill()
        raise WebflowSidecarError(f"sidecar timeout ({timeout_s}s) sobre {url}") from e

    if process.returncode != 0:
        raise WebflowSidecarError(
            f"sidecar exit={process.returncode}: {stderr.decode('utf-8', errors='replace')}"
        )

    try:
        data = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise WebflowSidecarError(f"sidecar stdout no es JSON válido: {e}") from e

    return WebflowSidecarResult(
        html=data["html"],
        url=data["url"],
        ix2_state=data.get("ix2_state"),
        page_timings=data.get("page_timings") or {},
        warnings=data.get("warnings") or [],
    )
