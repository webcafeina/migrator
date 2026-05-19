"""Cifrado/descifrado de credenciales del back del origen (v0.18.0).

Helpers Fernet duplicados del API (`apps/api/src/wcm_api/services/source_credentials.py`)
porque worker y API son apps separadas con dependencias propias —
extraer a un paquete compartido es scope para un futuro sprint cuando
sumemos más helpers de seguridad. Misma `FERNET_KEY` env var.

Si rotas la clave debes re-introducir las credenciales del origen (mismo
trade-off que `deploy_credentials_encrypted`).
"""

from __future__ import annotations

import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class FernetNotConfiguredError(Exception):
    """`FERNET_KEY` no presente o inválida en el entorno del worker."""


class CredentialsDecryptError(Exception):
    """El payload almacenado no descifra con la clave actual."""


def _fernet() -> Fernet:
    key = os.environ.get("FERNET_KEY")
    if not key:
        raise FernetNotConfiguredError(
            "FERNET_KEY no configurada en el entorno del worker."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise FernetNotConfiguredError(f"FERNET_KEY inválida: {e}") from e


def decrypt_source_credentials(ciphertext: str) -> dict[str, Any]:
    """Descifra el ciphertext almacenado y devuelve el dict original."""
    f = _fernet()
    try:
        raw = f.decrypt(ciphertext.encode("ascii"))
    except InvalidToken as e:
        raise CredentialsDecryptError(
            "Credenciales no descifrables con la FERNET_KEY actual del worker."
        ) from e
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise CredentialsDecryptError(
            f"Credenciales descifradas no son un dict: {type(parsed).__name__}"
        )
    return parsed
