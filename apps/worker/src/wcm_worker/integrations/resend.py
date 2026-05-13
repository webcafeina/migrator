"""Cliente Resend (email transaccional).

Wrappea el SDK oficial `resend` con:
- Construcción lazy desde env (`from_env`) — devuelve None sin API key.
- Reintentos sobre fallos transitorios del SDK (network).
- Verificación HMAC de webhooks entrantes (Resend usa Svix por debajo, pero
  expone también un signing secret simple por endpoint).

Política Webcafeína (ADR-025):
- El asunto y el cuerpo nunca se modifican aquí: ya vienen validados
  por OutreachComposerAgent (validador legal v1.0).
- `from_email` siempre es `migrator@webcafeina.com` (verificado en Resend);
  si quiere personalizarse por step, sobreescribir en `send(...)`.
- En producción tiene que estar el dominio verificado o Resend rechaza.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("wcm.worker.integrations.resend")


class ResendApiError(Exception):
    """Error genérico de la API de Resend."""


@dataclass(frozen=True)
class ResendSendResult:
    """Resultado de un envío."""

    message_id: str
    status: str = "queued"  # "queued" → entrega aún pendiente del MTA
    raw: dict[str, Any] | None = None


class ResendClient:
    """Cliente sincrónico. El SDK oficial es síncrono."""

    def __init__(
        self,
        api_key: str,
        *,
        default_from: str = "migrator@webcafeina.com",
        webhook_secret: str | None = None,
        max_retries: int = 3,
        retry_base_delay_s: float = 0.5,
        sdk_module: Any | None = None,
    ) -> None:
        if not api_key:
            raise ResendApiError("RESEND_API_KEY vacía")
        self.api_key = api_key
        self.default_from = default_from
        self.webhook_secret = webhook_secret
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s
        self._sdk = sdk_module  # inyectable para tests

    @classmethod
    def from_env(cls) -> "ResendClient | None":
        key = os.environ.get("RESEND_API_KEY", "").strip()
        if not key:
            return None
        return cls(
            api_key=key,
            default_from=os.environ.get("RESEND_FROM_EMAIL", "migrator@webcafeina.com"),
            webhook_secret=os.environ.get("RESEND_WEBHOOK_SECRET", "").strip() or None,
        )

    # ---------- public ----------

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
        from_email: str | None = None,
        reply_to: str | None = None,
        tags: list[dict[str, str]] | None = None,
    ) -> ResendSendResult:
        """Envía un email. Devuelve ResendSendResult con message_id."""
        if not to:
            raise ResendApiError("destinatarios vacíos")
        sdk = self._get_sdk()

        payload: dict[str, Any] = {
            "from": from_email or self.default_from,
            "to": to,
            "subject": subject,
            "text": body_text,
        }
        if body_html:
            payload["html"] = body_html
        if reply_to:
            payload["reply_to"] = reply_to
        if tags:
            payload["tags"] = tags

        attempt = 0
        last_exc: Exception | None = None
        while attempt < self.max_retries:
            attempt += 1
            try:
                resp = sdk.Emails.send(payload)
            except Exception as e:  # noqa: BLE001 — el SDK no tipifica errores
                last_exc = e
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_base_delay_s * (2 ** (attempt - 1)))
                continue
            if not isinstance(resp, dict) or not resp.get("id"):
                raise ResendApiError(f"Respuesta inesperada: {resp!r}")
            return ResendSendResult(message_id=str(resp["id"]), raw=resp)
        raise ResendApiError(f"Resend send falló tras {self.max_retries} intentos: {last_exc}")

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        """HMAC SHA-256 hex sobre el body crudo. Si webhook_secret no está
        configurado, devuelve False (no aceptar nada sin verificar).
        """
        if not self.webhook_secret or not signature:
            return False
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ---------- internals ----------

    def _get_sdk(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        try:
            import resend  # type: ignore
        except ImportError as e:
            raise ResendApiError("SDK `resend` no instalado") from e
        resend.api_key = self.api_key
        return resend
