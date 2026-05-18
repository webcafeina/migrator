from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, ConfigDict, Field

from wcm_types.enums import OutreachChannel, OutreachSendStatus, OutreachSequenceStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class OutreachStep(WcmModel):
    """Un paso dentro de steps_json — validado para asegurar mínimos LSSI-CE.

    Tolerante con shapes legacy (fix v0.11.1): sequences viejas
    persistidas en BD tienen `delay_days` (sin `_from_previous`) y
    pueden traer campos extra (`template`). Para no romper su lectura
    desde el dashboard:

    - `step_index` opcional con default 0 (se infiere del orden si falta).
    - `delay_days_from_previous` acepta también el alias `delay_days`
      vía `AliasChoices`.
    - `extra="allow"` permite cualquier campo adicional sin lanzar 500.
      Los composers nuevos siguen escribiendo solo el shape canónico.
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="allow",  # tolerancia a sequences legacy en BD
        populate_by_name=True,
    )

    step_index: int = Field(default=0, ge=0)
    subject: str | None = Field(default=None, max_length=255)
    body: str
    delay_days_from_previous: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices(
            "delay_days_from_previous", "delay_days"
        ),
    )
    legal_footer_included: bool = True


class OutreachSequenceBase(WcmModel):
    template_name: str = Field(max_length=80)
    name: str = Field(max_length=255)
    channel: OutreachChannel = OutreachChannel.EMAIL
    steps_json: list[OutreachStep]


class OutreachSequenceCreate(OutreachSequenceBase):
    lead_id: int


class OutreachSequenceRead(OutreachSequenceBase, TimestampedRead):
    id: int
    lead_id: int
    status: OutreachSequenceStatus
    legal_validation_passed: bool
    legal_validator_version: str | None


class OutreachSendRead(WcmModel):
    id: int
    sequence_id: int
    lead_id: int
    step_index: int
    channel: OutreachChannel
    subject: str | None
    body_rendered: str | None
    status: OutreachSendStatus
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    bounced_at: datetime | None
    provider_message_id: str | None
    created_at: datetime
    updated_at: datetime
