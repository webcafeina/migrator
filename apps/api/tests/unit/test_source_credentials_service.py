"""Tests del helper Fernet `services/source_credentials.py` (v0.18.0)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from wcm_api.services.source_credentials import (
    CredentialsDecryptError,
    FernetNotConfiguredError,
    decrypt_source_credentials,
    encrypt_source_credentials,
)


def test_encrypt_decrypt_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    payload = {"api_key": "secret-key", "site_id": "site-123"}
    ciphertext = encrypt_source_credentials(payload)
    assert isinstance(ciphertext, str)
    assert "secret-key" not in ciphertext
    decrypted = decrypt_source_credentials(ciphertext)
    assert decrypted == payload


def test_sin_fernet_key_levanta_error(monkeypatch) -> None:
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(FernetNotConfiguredError, match="no configurada"):
        encrypt_source_credentials({"x": "y"})


def test_fernet_key_invalida_levanta_error(monkeypatch) -> None:
    monkeypatch.setenv("FERNET_KEY", "this-is-not-base64-32-bytes")
    with pytest.raises(FernetNotConfiguredError, match="inválida"):
        encrypt_source_credentials({"x": "y"})


def test_descifrar_con_clave_distinta_levanta_credentialsdecrypterror(monkeypatch) -> None:
    """Simula rotación de FERNET_KEY: lo cifrado con K1 no descifra con K2."""
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    ciphertext = encrypt_source_credentials({"api_key": "secret"})
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    with pytest.raises(CredentialsDecryptError, match="re-introduce"):
        decrypt_source_credentials(ciphertext)
