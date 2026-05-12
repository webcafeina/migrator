from __future__ import annotations

import uuid

from pydantic import EmailStr, Field

from wcm_types.enums import UserRole
from wcm_types.schemas._base import TimestampedRead, WcmModel


class UserBase(WcmModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=255)


class UserRead(UserBase, TimestampedRead):
    id: uuid.UUID
