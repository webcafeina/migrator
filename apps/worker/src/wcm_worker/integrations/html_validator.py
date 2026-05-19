"""Validador HTML W3C vía API pública nu.validator.org (v0.16.0).

Endpoint: `https://validator.w3.org/nu/?out=json` con HTML POST en
body Content-Type: text/html. Devuelve JSON con `messages[]`
(type=error/info, message, line, column, extract, ...).

Rate-limit: el W3C asks 1 req/segundo. Aplicamos cliente-side
sleep 1.2s entre requests (margen). Para sites grandes la fase QA
limita a 50 páginas máximo.

Si la API responde 429 o timeout, devolvemos resultado vacío
(`errors=[]`) — mejor reportar 0 errores que romper la fase.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("wcm.worker.integrations.html_validator")

W3C_API_URL = "https://validator.w3.org/nu/?out=json"
REQUEST_INTERVAL_S = 1.2
TIMEOUT_S = 30


@dataclass(frozen=True)
class ValidatorError:
    """Un mensaje del validador (error o warning)."""

    type: str  # "error" | "info" (W3C usa "info" para warnings)
    message: str
    line: int | None = None
    column: int | None = None
    extract: str | None = None


@dataclass
class ValidatorResult:
    """Resultado por página validada."""

    url: str
    errors: list[ValidatorError] = field(default_factory=list)
    warnings: list[ValidatorError] = field(default_factory=list)


_last_request_at: float = 0.0


def _throttle() -> None:
    """Sleep para respetar el rate-limit del W3C (1 req/s)."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < REQUEST_INTERVAL_S:
        time.sleep(REQUEST_INTERVAL_S - elapsed)
    _last_request_at = time.monotonic()


def validate_html(
    html: str,
    url: str,
    *,
    http_client: httpx.Client | None = None,
) -> ValidatorResult:
    """POST HTML al validador W3C. Errores/warnings → ValidatorResult.

    Devolvemos ValidatorResult con errors/warnings VACÍAS en caso de
    fallo del API (timeout, 429, JSON malformado). El agent caller lo
    documenta en `warnings` del AgentResult.
    """
    _throttle()

    client = http_client or httpx.Client(timeout=TIMEOUT_S)
    own_client = http_client is None
    try:
        try:
            resp = client.post(
                W3C_API_URL,
                content=html.encode("utf-8"),
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            log.warning(
                "html_validator_request_failed",
                extra={"url": url, "error": str(e)},
            )
            return ValidatorResult(url=url)

        if resp.status_code != 200:
            log.warning(
                "html_validator_non_200",
                extra={"url": url, "status": resp.status_code},
            )
            return ValidatorResult(url=url)

        try:
            data = resp.json()
        except ValueError as e:
            log.warning("html_validator_parse_failed", extra={"url": url, "error": str(e)})
            return ValidatorResult(url=url)

        errors: list[ValidatorError] = []
        warnings: list[ValidatorError] = []
        for msg in data.get("messages", []) or []:
            ve = ValidatorError(
                type=str(msg.get("type", "")),
                message=str(msg.get("message", "")),
                line=msg.get("lastLine") or msg.get("firstLine"),
                column=msg.get("lastColumn") or msg.get("firstColumn"),
                extract=msg.get("extract"),
            )
            if ve.type == "error":
                errors.append(ve)
            else:
                warnings.append(ve)
        return ValidatorResult(url=url, errors=errors, warnings=warnings)
    finally:
        if own_client:
            client.close()
