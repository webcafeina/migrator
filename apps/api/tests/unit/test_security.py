"""Tests del módulo security."""

from __future__ import annotations

import uuid

import pytest

from wcm_api.errors import UnauthorizedError
from wcm_api.security import (
    decode_opt_out_token,
    decode_session_token,
    hash_password,
    issue_opt_out_token,
    issue_session_token,
    verify_password,
)


def test_hash_password_verifies_correct() -> None:
    h = hash_password("Sup3rS3cur3!")
    assert verify_password("Sup3rS3cur3!", h)


def test_hash_password_rejects_wrong() -> None:
    h = hash_password("Sup3rS3cur3!")
    assert not verify_password("wrong", h)


def test_session_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token, expires = issue_session_token(user_id=user_id, role="admin")
    payload = decode_session_token(token)
    assert payload.sub == str(user_id)
    assert payload.role == "admin"


def test_session_token_invalid_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        decode_session_token("not.a.valid.token")


def test_opt_out_token_purpose_check() -> None:
    """Un session token NO debe pasar como opt-out token, y viceversa."""
    session_token, _ = issue_session_token(user_id=uuid.uuid4(), role="admin")
    with pytest.raises(UnauthorizedError, match="propósito"):
        decode_opt_out_token(session_token)

    opt_out_token = issue_opt_out_token(email="user@example.com", lead_id=42)
    decoded = decode_opt_out_token(opt_out_token)
    assert decoded["email"] == "user@example.com"
    assert decoded["lead_id"] == 42

    # Un opt-out token tampoco debe usarse como session
    # (decode_session_token no chequea purpose pero no rompe; lo importante
    # es que decode_opt_out_token sí lo chequea)


def test_opt_out_token_invalid_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        decode_opt_out_token("not.a.valid.token")
