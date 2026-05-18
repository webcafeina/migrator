from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, HttpUrl

from wcm_types.enums import BuilderType, LeadStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class LeadBase(WcmModel):
    url: HttpUrl
    business_name: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    country: str = Field(default="ES", min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)


class LeadCreate(LeadBase):
    """Payload de descubrimiento — solo campos derivables sin enrichment.

    Usado por:
    - `POST /api/v1/leads` (alta manual desde dashboard o CLI).
    - ProspectorAgent internamente al insertar leads descubiertos por
      campaña (no recibe esto vía HTTP, construye el modelo directamente).
    """


class LeadUpdate(WcmModel):
    business_name: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    emails: list[EmailStr] | None = None
    phones: list[str] | None = None
    social_links: dict[str, str] | None = None
    status: LeadStatus | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    builder_detected: BuilderType | None = None
    builder_confidence: float | None = Field(default=None, ge=0, le=1)
    builder_evidence: list[dict[str, Any]] | None = None


class LeadRead(LeadBase, TimestampedRead):
    id: int
    builder_detected: BuilderType | None
    builder_confidence: float | None
    builder_evidence: list[dict[str, Any]] | None
    emails: list[str]
    phones: list[str]
    social_links: dict[str, str]
    status: LeadStatus
    score: int
    last_crawl_at: datetime | None
    embedding_model: str | None
    embedding_at: datetime | None
    # embedding (vector 1024) NUNCA se serializa al cliente: demasiado pesado y no aporta


class LeadBulkCreate(WcmModel):
    """Alta de múltiples leads en una sola request.

    Los campos opcionales (sector, region, country, business_name) se
    aplican a TODAS las URLs del batch — útil cuando el operador pega
    una lista homogénea (todas del mismo sector/región).
    """

    urls: list[HttpUrl] = Field(min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    country: str = Field(default="ES", min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)


class LeadBulkCreateOutcome(WcmModel):
    """Detalle por URL fallida o duplicada en un alta bulk.

    `lead_id` se rellena cuando el outcome es 'skipped_duplicate' (id
    del lead existente que ya tenía la URL). `reason` se rellena cuando
    el outcome es 'failed'.
    """

    url: str
    outcome: str  # "skipped_duplicate" | "failed"
    lead_id: int | None = None
    reason: str | None = None


class LeadBulkCreateResult(WcmModel):
    """Respuesta agregada del `POST /api/v1/leads/bulk`.

    Listas separadas para facilitar el render en dashboard sin tener
    que filtrar por outcome. `created` lleva LeadRead completos para
    que el cliente no tenga que hacer follow-up fetches.
    """

    created: list[LeadRead]
    skipped_duplicates: list[LeadBulkCreateOutcome]
    failed: list[LeadBulkCreateOutcome]


class LeadEnrichmentBase(WcmModel):
    source: str = Field(max_length=80)
    employees_estimate: int | None = Field(default=None, ge=0)
    revenue_estimate_eur: int | None = Field(default=None, ge=0)
    tech_stack: list[str] | None = None
    traffic_estimate_monthly: int | None = Field(default=None, ge=0)
    ahrefs_dr: float | None = Field(default=None, ge=0, le=100)
    legal_ground: str | None = Field(default=None, max_length=40)
    raw_payload: dict[str, Any] | None = None


class LeadEnrichmentCreate(LeadEnrichmentBase):
    lead_id: int


class LeadEnrichmentRead(LeadEnrichmentBase, TimestampedRead):
    id: int
    lead_id: int


class OptOutLogRead(WcmModel):
    id: int
    email: EmailStr
    lead_id_at_optout: int | None
    channel: str
    evidence: str | None
    opted_out_at: datetime
