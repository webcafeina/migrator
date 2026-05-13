"""CRUD de usuarios — solo admin."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.users import User
from wcm_types.enums import UserRole
from wcm_types.schemas.users import UserCreate, UserRead

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.security import hash_password, require_role

router = APIRouter(prefix="/users", tags=["users"])

_admin_only = require_role(UserRole.ADMIN.value)


@router.get("", response_model=list[UserRead])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> list[UserRead]:
    users = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> UserRead:
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Email ya en uso: {payload.email}")

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        name=payload.name,
        role=payload.role,
        is_active=payload.is_active,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> UserRead:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Usuario {user_id} no encontrado")
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Usuario {user_id} no encontrado")
    await session.delete(user)
    await session.commit()
