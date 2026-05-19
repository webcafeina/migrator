"""Wrapper de Lighthouse CLI vía subprocess (v0.16.0).

Lighthouse es Node.js, no Python. Se instala global en el server del
worker: `npm install -g lighthouse@^12`. El binario `lighthouse` debe
estar en PATH para que `subprocess.run` lo encuentre.

Decisión vs alternativas:
- PageSpeed Insights API (gratis, hosted): requiere quota Google,
  rate-limit, depende de servicio externo. Para v0.16.0 evitamos esa
  dependencia — Lighthouse local es más predecible y no expone
  nuestros URLs internos a Google.
- Lighthouse npm lib (`require("lighthouse")` desde Node script):
  más control pero suma código JS al repo. CLI es trade-off OK.

Si el binario no está disponible, `run_lighthouse` lanza
`LighthouseNotAvailableError` para que el agent caller marque
SKIPPED + cree residual task con instrucciones.

Output: `LighthouseResult` con scores 0-100 (redondeados a int) por
categoría. Lighthouse devuelve 0.0-1.0 internamente — multiplicamos.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger("wcm.worker.integrations.lighthouse")

#: Timeout total del subprocess (incluye Chromium boot + análisis).
DEFAULT_TIMEOUT_S = 120

FormFactor = Literal["desktop", "mobile"]


class LighthouseNotAvailableError(RuntimeError):
    """`lighthouse` binario no encontrado en PATH. El operador debe
    `npm install -g lighthouse@^12` en el server del worker."""


@dataclass(frozen=True)
class LighthouseResult:
    """Scores 0-100 por categoría. None si no medido."""

    performance: int | None
    accessibility: int | None
    best_practices: int | None
    seo: int | None
    raw_json: dict | None = None
    """JSON completo del reporte Lighthouse para drill-down."""


def lighthouse_available() -> bool:
    """True si el binario `lighthouse` está en PATH."""
    return shutil.which("lighthouse") is not None


def run_lighthouse(
    url: str,
    *,
    form_factor: FormFactor = "desktop",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> LighthouseResult:
    """Ejecuta `lighthouse URL --output=json --output-path=<tmp>` y
    parsea el resultado. Lanza `LighthouseNotAvailableError` si el
    binario no está disponible.

    `form_factor` controla viewport + throttling: `desktop` (1350x940,
    sin throttling) vs `mobile` (412x823, throttling 3G simulado).
    """
    if not lighthouse_available():
        raise LighthouseNotAvailableError(
            "`lighthouse` no está en PATH. Instala con: `npm install -g lighthouse@^12`."
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        report_path = Path(tmp.name)

    try:
        args = [
            "lighthouse",
            url,
            "--quiet",
            "--output=json",
            f"--output-path={report_path}",
            "--chrome-flags=--headless --no-sandbox --disable-gpu",
            "--only-categories=performance,accessibility,best-practices,seo",
        ]
        if form_factor == "mobile":
            args.append("--preset=mobile")
        else:
            args.extend(["--form-factor=desktop", "--screenEmulation.disabled"])

        proc = subprocess.run(  # noqa: S603 — argv controlado, sin shell=True
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if proc.returncode != 0:
            log.warning(
                "lighthouse_subprocess_nonzero",
                extra={"url": url, "returncode": proc.returncode, "stderr": proc.stderr[:500]},
            )
            return LighthouseResult(
                performance=None,
                accessibility=None,
                best_practices=None,
                seo=None,
            )

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("lighthouse_report_parse_failed", extra={"url": url, "error": str(e)})
            return LighthouseResult(
                performance=None,
                accessibility=None,
                best_practices=None,
                seo=None,
            )

        categories = data.get("categories", {}) or {}
        return LighthouseResult(
            performance=_extract_score(categories.get("performance")),
            accessibility=_extract_score(categories.get("accessibility")),
            best_practices=_extract_score(categories.get("best-practices")),
            seo=_extract_score(categories.get("seo")),
            raw_json=data,
        )
    except subprocess.TimeoutExpired:
        log.warning("lighthouse_timeout", extra={"url": url, "timeout_s": timeout_s})
        return LighthouseResult(
            performance=None,
            accessibility=None,
            best_practices=None,
            seo=None,
        )
    finally:
        try:
            report_path.unlink(missing_ok=True)
        except OSError:
            pass


def _extract_score(category: dict | None) -> int | None:
    """Lighthouse devuelve `score: 0.0-1.0`. Devolvemos 0-100 int o None."""
    if not category or "score" not in category or category["score"] is None:
        return None
    try:
        return round(float(category["score"]) * 100)
    except (TypeError, ValueError):
        return None
