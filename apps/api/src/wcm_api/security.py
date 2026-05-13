"""Seguridad: hashing de contraseñas (argon2), emisión/verificación de JWT,
cookie http-only para sesión, dependency `get_current_user`.

Notas de diseño:
- Argon2 sobre bcrypt: más resistente a hardware especializado y configurable.
- JWT en cookie http-only `wcm_session` (configurable). El dashboard
  envía la cookie automáticamente; el CLI puede usar `Authorization: Bearer`.
- Roles: admin / operator / viewer (definidos en wcm_types.enums.UserRole).
  El dashboard expone solo lo que el rol permite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.config import ApiSettings, get_settings
from wcm_api.db import get_session
from wcm_api.errors import ForbiddenError, UnauthorizedError

_hasher = PasswordHasher()


# ---------- Password hashing ----------

def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# ---------- JWT ----------

@dataclass(frozen=True)
class TokenPayload:
    sub: str  # user id (uuid)
    role: str
    exp: datetime
    iat: datetime
    jti: str


def issue_session_token(
    *, user_id: uuid.UUID, role: str, settings: ApiSettings | None = None
) -> tuple[str, datetime]:
    """Emite un JWT de sesión. Devuelve (token, expires_at)."""
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=s.jwt_expiry_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, expires


def decode_session_token(token: str, *, settings: ApiSettings | None = None) -> TokenPayload:
    s = settings or get_settings()
    try:
        decoded = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError("Sesión expirada") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError("Token inválido") from e
    return TokenPayload(
        sub=decoded["sub"],
        role=decoded["role"],
        exp=datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
        iat=datetime.fromtimestamp(decoded["iat"], tz=timezone.utc),
        jti=decoded["jti"],
    )


# ---------- Opt-out tokens (RGPD) — separado del JWT de sesión ----------

def issue_opt_out_token(
    *, email: str, lead_id: int | None = None, settings: ApiSettings | None = None
) -> str:
    """Firma un token de opt-out RGPD.

    NO caduca (los opt-out no caducan), pero lleva `iat` y `jti` por si
    quisiéramos revocar uno comprometido. Se distingue del session token
    por el claim `purpose=opt_out`.
    """
    s = settings or get_settings()
    payload = {
        "purpose": "opt_out",
        "email": email,
        "lead_id": lead_id,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_opt_out_token(token: str, *, settings: ApiSettings | None = None) -> dict:
    s = settings or get_settings()
    try:
        decoded = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError("Token opt-out inválido") from e
    if decoded.get("purpose") != "opt_out":
        raise UnauthorizedError("Token con propósito incorrecto")
    return decoded


# ---------- Dependencies ----------

async def get_token_from_request(
    session_cookie: Annotated[str | None, Cookie(alias=None)] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[ApiSettings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> str:
    """Extrae el token JWT de la cookie de sesión o del header Authorization.

    No valida (eso lo hace `get_current_user_payload`). Si no hay token,
    lanza UnauthorizedError.
    """
    # session_cookie depende del nombre dinámico (settings.session_cookie_name),
    # así que reextraemos manualmente desde el header Cookie. FastAPI no
    # soporta nombres dinámicos en el Cookie() decorator, así que
    # implementamos el lookup nosotros más abajo. Mantenemos esta función
    # como conveniencia para Authorization Bearer.
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise UnauthorizedError("Credenciales no proporcionadas")


async def get_current_user_payload(
    request_state_token: Annotated[str | None, Header(alias="x-wcm-token")] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[ApiSettings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> TokenPayload:
    """Dependency principal de autenticación.

    Acepta token en (orden de preferencia):
    1. Cookie `<session_cookie_name>` (vía middleware que la inyecta como header)
    2. Header `Authorization: Bearer <token>`
    3. Header `x-wcm-token` (uso CLI sin Bearer)
    """
    token: str | None = None

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif request_state_token:
        token = request_state_token.strip()

    if not token:
        raise UnauthorizedError("Credenciales no proporcionadas")

    return decode_session_token(token, settings=settings)


def require_role(*allowed_roles: str):
    """Factory de dependency que exige rol(es) específicos."""

    async def _checker(
        payload: Annotated[TokenPayload, Depends(get_current_user_payload)],
    ) -> TokenPayload:
        if payload.role not in allowed_roles:
            raise ForbiddenError(
                f"Acceso denegado: rol '{payload.role}' no autorizado",
                details={"required": list(allowed_roles)},
            )
        return payload

    return _checker
