from __future__ import annotations

from datetime import datetime

from pydantic import Field

from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class ResidualTaskBase(WcmModel):
    title: str = Field(max_length=255)
    description: str
    category: ResidualCategory
    estimated_minutes: int | None = Field(default=None, ge=0)
    screenshot_paths: list[str] = Field(default_factory=list)
    generated_by: str | None = Field(default=None, max_length=64)
    assignee_hint: str | None = Field(default=None, max_length=64)


class ResidualTaskCreate(ResidualTaskBase):
    project_id: int


class ResidualTaskRead(ResidualTaskBase, TimestampedRead):
    id: int
    project_id: int
    clickup_task_id: str | None
    status: ResidualStatus
    closed_at: datetime | None
