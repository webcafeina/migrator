"""Base de los schemas Pydantic — config compartida."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WcmModel(BaseModel):
    """Base con config estricta para todos los schemas Webcafeína Migrator."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )


class TimestampedRead(WcmModel):
    created_at: datetime
    updated_at: datetime
