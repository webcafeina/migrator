"""Cifrado/descifrado de credenciales del back del origen (v0.18.0).

Helpers Fernet (cryptography) para `projects.source_credentials_encrypted`.
Misma clave (`FERNET_KEY` env) que la prevista para
`deploy_credentials_encrypted` — rotar requiere re-introducir ambos.

Estructura JSON cifrada depende del builder:
- Wix:     `{"api_key": "...", "site_id": "..."}`
- Webflow: `{"api_token": "...", "site_id": "..."}`

El cifrado garantiza que un dump de BD no expone tokens en claro.
Las credenciales NUNCA viajan en `ProjectRead` (el endpoint que las
devuelve es separado y admin-only, y descifra al vuelo).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("wcm.api.source_credentials")


class FernetNotConfiguredError(Exception):
    """`FERNET_KEY` no presente en el entorno. El endpoint que intente
    cifrar/descifrar debe devolver 503."""


class CredentialsDecryptError(Exception):
    """El payload almacenado no descifra con la clave actual.
    Causa típica: rotación de `FERNET_KEY` sin re-introducir credenciales."""


def _fernet() -> Fernet:
    key = os.environ.get("FERNET_KEY")
    if not key:
        raise FernetNotConfiguredError(
            "FERNET_KEY no configurada en el entorno. "
            "Genera una con `python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` y añádela al .env."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise FernetNotConfiguredError(
            f"FERNET_KEY presente pero inválida (debe ser 32 bytes base64): {e}"
        ) from e


def encrypt_source_credentials(plaintext: dict[str, Any]) -> str:
    """Cifra el dict como JSON UTF-8 y devuelve un string base64 storage-safe.

    Reversible solo con `decrypt_source_credentials` + la misma `FERNET_KEY`.
    """
    f = _fernet()
    raw = json.dumps(plaintext, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f.encrypt(raw).decode("ascii")


def decrypt_source_credentials(ciphertext: str) -> dict[str, Any]:
    """Descifra un string previamente cifrado. Lanza
    `CredentialsDecryptError` si la clave actual no corresponde."""
    f = _fernet()
    try:
        raw = f.decrypt(ciphertext.encode("ascii"))
    except InvalidToken as e:
        raise CredentialsDecryptError(
            "Credenciales no descifrables con la FERNET_KEY actual. "
            "Probable rotación de clave; re-introduce las credenciales del origen."
        ) from e
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise CredentialsDecryptError(
            f"Credenciales descifradas no son un dict: {type(parsed).__name__}"
        )
    return parsed
