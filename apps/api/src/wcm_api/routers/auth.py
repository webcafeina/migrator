"""Auth flow: login, logout, me.

Estrategia:
- `POST /auth/login` con body {email, password} → setea cookie http-only
  con el JWT y devuelve `UserRead`.
- `POST /auth/logout` borra la cookie.
- `GET /auth/me` devuelve el usuario actual.

Para el dashboard (Next.js) la cookie llega automáticamente. Para CLI
clients usar `Authorization: Bearer <token>` o `x-wcm-token`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.users import User
from wcm_types.schemas.users import UserRead

from wcm_api.config import ApiSettings, get_settings
from wcm_api.db import get_session
from wcm_api.errors import UnauthorizedError
from wcm_api.rate_limit import limiter
from wcm_api.security import (
    TokenPayload,
    get_current_user_payload,
    issue_session_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=UserRead)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: LoginPayload,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> UserRead:
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        # Mismo mensaje para email-not-found y wrong-password (anti-enumeración)
        raise UnauthorizedError("Credenciales inválidas")

    token, expires = issue_session_token(
        user_id=user.id, role=user.role.value, settings=settings
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        expires=int((expires - datetime.now(timezone.utc)).total_seconds()),
        path="/",
    )
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> Response:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(
    payload: Annotated[TokenPayload, Depends(get_current_user_payload)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    user = await session.get(User, uuid.UUID(payload.sub))
    if user is None or not user.is_active:
        raise UnauthorizedError("Usuario no encontrado o inactivo")
    return UserRead.model_validate(user)
