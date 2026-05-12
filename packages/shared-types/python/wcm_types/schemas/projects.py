from __future__ import annotations

from datetime import datetime
from typing import Any

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
    status: ProjectStatus
    started_at: datetime | None
    completed_at: datetime | None
    estimated_go_live_at: datetime | None


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
