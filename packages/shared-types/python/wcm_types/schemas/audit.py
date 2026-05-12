from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from wcm_types.enums import AuditAction, ErrorSeverity
from wcm_types.schemas._base import WcmModel


class AuditLogRead(WcmModel):
    id: uuid.UUID
    at: datetime
    actor: str = Field(max_length=64)
    action: AuditAction
    entity_type: str | None
    entity_id: str | None
    payload: dict[str, Any] | None
    legal_ground: str | None


class ErrorLogRead(WcmModel):
    id: uuid.UUID
    at: datetime
    project_id: int | None
    severity: ErrorSeverity
    component: str = Field(max_length=64)
    message: str
    stack: str | None
    context_json: dict[str, Any] | None
    sentry_event_id: str | None
    notified_at: datetime | None
