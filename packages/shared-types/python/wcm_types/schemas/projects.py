from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, HttpUrl

from wcm_types.enums import BuilderType, ProjectPhaseStatus, ProjectStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class ProjectBase(WcmModel):
    client_name: str = Field(max_length=255)
    source_url: HttpUrl
    target_domain: str | None = Field(default=None, max_length=255)
    builder_source: BuilderType | None = None
    has_ecommerce: bool = False
    is_multilang: bool = False
    langs: list[str] = Field(default_factory=list)
    primary_lang: str | None = Field(default=None, max_length=8)
    asset_storage: str = Field(default="wp_local", pattern="^(r2|wp_local)$")
    preserve_paths: bool = True
    plan: str | None = Field(default=None, max_length=40)


class ProjectCreate(ProjectBase):
    lead_id: int | None = None
    hosting_target_json: dict[str, Any] | None = None


class ProjectUpdate(WcmModel):
    client_name: str | None = Field(default=None, max_length=255)
    target_domain: str | None = Field(default=None, max_length=255)
    builder_source: BuilderType | None = None
    has_ecommerce: bool | None = None
    is_multilang: bool | None = None
    langs: list[str] | None = None
    primary_lang: str | None = Field(default=None, max_length=8)
    asset_storage: str | None = Field(default=None, pattern="^(r2|wp_local)$")
    preserve_paths: bool | None = None
    status: ProjectStatus | None = None
    plan: str | None = Field(default=None, max_length=40)
    estimated_go_live_at: datetime | None = None


class ProjectRead(ProjectBase, TimestampedRead):
    id: int
    lead_id: int | None
    hosting_target_json: dict[str, Any] | None
    theme_styles_origin: dict[str, Any] | None
    visual_diff_avg_score: float | None
    # v0.16.0 — URLs R2 del entregable PDF + MD. Pobladas por
    # checklist-generator. null hasta que el agent ejecute.
    checklist_md_url: str | None = None
    checklist_pdf_url: str | None = None
    # v0.18.0 — acceso al back del origen + cache preflight.
    # Las credenciales NUNCA se exponen en claro; solo el modo es público.
    source_access_mode: Literal["none", "api", "full"] = "none"
    has_source_credentials: bool = False
    preflight_results_json: dict[str, Any] | None = None
    preflight_at: datetime | None = None
    status: ProjectStatus
    started_at: datetime | None
    completed_at: datetime | None
    estimated_go_live_at: datetime | None


# ---------- v0.18.0: source credentials por builder ----------


class WixSourceCredentials(WcmModel):
    """Credenciales para Wix REST v3 (Wix Headless API)."""

    builder: Literal["wix"]
    api_key: str = Field(min_length=20, max_length=512)
    site_id: str = Field(min_length=8, max_length=64)


class WebflowSourceCredentials(WcmModel):
    """Credenciales para Webflow Sites/CMS API v2."""

    builder: Literal["webflow"]
    api_token: str = Field(min_length=20, max_length=512)
    site_id: str = Field(min_length=8, max_length=64)


#: Union discriminada por el campo `builder`. Cualquier futuro adapter
#: (Squarespace, Shopify, Hostinger) añade su tipo aquí y FastAPI valida
#: el payload de PUT /source-credentials automáticamente.
SourceCredentialsUpdate = Annotated[
    WixSourceCredentials | WebflowSourceCredentials,
    Field(discriminator="builder"),
]


# ---------- v0.18.0: preflight ----------


class PreflightCheck(WcmModel):
    """Resultado de un check individual del preflight."""

    ok: bool
    message: str
    blocking: bool = False
    extras: dict[str, Any] | None = None


class PreflightResult(WcmModel):
    """Respuesta completa de POST /projects/{id}/preflight."""

    wp_target: PreflightCheck
    plugins: dict[str, bool]  # {"bricks": True, "gravity_forms": True, ...}
    source: PreflightCheck
    source_credentials: PreflightCheck
    can_start: bool
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    executed_at: datetime


class ProjectPhaseRead(WcmModel):
    id: int
    project_id: int
    phase_name: str
    status: ProjectPhaseStatus
    started_at: datetime | None
    completed_at: datetime | None
    attempt: int
    error_log: str | None
    output_summary: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
