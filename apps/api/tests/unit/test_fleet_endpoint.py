"""Tests del endpoint GET /api/v1/projects/fleet (v0.19.0).

Verifica la agregación de las 15 fases en 5 buckets canónicos y los
helpers de prioridad (failed > running > pending > completed > skipped).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_api.routers.projects import (
    _BUCKET_ORDER,
    _PHASE_BUCKETS,
    _aggregate_bucket_status,
)
from wcm_types.enums import (
    BuilderType,
    ProjectPhaseStatus,
    ProjectStatus,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_row(
    *,
    pid: int = 7,
    status: ProjectStatus = ProjectStatus.RUNNING,
    builder: BuilderType | None = BuilderType.WIX,
) -> MagicMock:
    p = MagicMock()
    p.id = pid
    p.client_name = "Bar Pepe"
    p.source_url = "https://barpepe.es"
    p.target_domain = "barpepe.com"
    p.builder_source = builder
    p.status = status
    p.visual_diff_avg_score = 0.92
    p.has_ecommerce = False
    p.is_multilang = False
    p.started_at = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    p.created_at = datetime(2026, 5, 19, 11, 0, tzinfo=UTC)
    p.updated_at = datetime(2026, 5, 19, 12, 5, tzinfo=UTC)
    return p


def test_phase_buckets_cubre_15_fases_canonicas() -> None:
    """Las 15 fases del pipeline deben mapear a uno de los 5 buckets."""
    canonical_phases = {
        "scrape_origin",
        "extract_content",
        "preserve_seo",
        "optimize_assets",
        "detect_multilang",
        "transpile_bricks",
        "deploy_wp",
        "migrate_woo",
        "configure_wpml",
        "rebuild_forms",
        "visual_diff",
        "qa",
        "generate_checklist",
        "sync_clickup",
        "notify",
    }
    for ph in canonical_phases:
        assert ph in _PHASE_BUCKETS, f"Fase '{ph}' sin bucket asignado"
    for bucket in _PHASE_BUCKETS.values():
        assert bucket in _BUCKET_ORDER, f"Bucket '{bucket}' no canónico"


def test_aggregate_failed_gana_sobre_todo() -> None:
    assert _aggregate_bucket_status(["completed", "failed", "running"]) == "failed"


def test_aggregate_running_gana_sobre_pending() -> None:
    assert _aggregate_bucket_status(["completed", "running"]) == "running"


def test_aggregate_all_completed_es_completed() -> None:
    assert _aggregate_bucket_status(["completed", "completed"]) == "completed"


def test_aggregate_all_skipped_es_skipped() -> None:
    assert _aggregate_bucket_status(["skipped", "skipped"]) == "skipped"


def test_aggregate_completed_mas_skipped_es_completed() -> None:
    """Mixed completed+skipped → considera el bucket cerrado completed."""
    assert _aggregate_bucket_status(["completed", "skipped"]) == "completed"


def test_aggregate_vacio_es_pending() -> None:
    assert _aggregate_bucket_status([]) == "pending"


def test_aggregate_solo_pending_es_pending() -> None:
    assert _aggregate_bucket_status(["pending", "pending"]) == "pending"


@pytest.mark.asyncio
async def test_endpoint_fleet_vacio(client, fake_session, viewer_token) -> None:
    """Sin proyectos → []."""
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute = AsyncMock(return_value=empty_result)
    resp = await client.get("/api/v1/projects/fleet", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_endpoint_fleet_proyecto_sin_fases(
    client, fake_session, viewer_token
) -> None:
    """Proyecto sin fases registradas → phase_summary todo 'pending'."""
    project = _project_row()
    projects_result = MagicMock()
    projects_result.scalars = MagicMock(return_value=MagicMock(all=lambda: [project]))
    # Sin fases.
    phases_result = MagicMock()
    phases_result.all = MagicMock(return_value=[])

    fake_session.execute = AsyncMock(side_effect=[projects_result, phases_result])
    resp = await client.get("/api/v1/projects/fleet", headers=_auth(viewer_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == 7
    assert body[0]["phase_summary"] == {
        "scrape": "pending",
        "transpile": "pending",
        "deploy": "pending",
        "qa": "pending",
        "notify": "pending",
    }


@pytest.mark.asyncio
async def test_endpoint_fleet_agregacion_buckets(
    client, fake_session, viewer_token
) -> None:
    """Con varias fases por bucket, agrega correctamente al status canónico."""
    project = _project_row()
    projects_result = MagicMock()
    projects_result.scalars = MagicMock(return_value=MagicMock(all=lambda: [project]))
    # Fases: scrape_origin completed + extract_content completed → scrape=completed
    #        deploy_wp running                                  → deploy=running
    #        qa failed                                          → qa=failed
    phases_result = MagicMock()
    phases_result.all = MagicMock(
        return_value=[
            (7, "scrape_origin", ProjectPhaseStatus.COMPLETED),
            (7, "extract_content", ProjectPhaseStatus.COMPLETED),
            (7, "deploy_wp", ProjectPhaseStatus.RUNNING),
            (7, "qa", ProjectPhaseStatus.FAILED),
        ]
    )
    fake_session.execute = AsyncMock(side_effect=[projects_result, phases_result])
    resp = await client.get("/api/v1/projects/fleet", headers=_auth(viewer_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body[0]["phase_summary"]["scrape"] == "completed"
    assert body[0]["phase_summary"]["deploy"] == "running"
    assert body[0]["phase_summary"]["qa"] == "failed"
    assert body[0]["current_phase_name"] in {"deploy_wp", "extract_content", "scrape_origin"}


@pytest.mark.asyncio
async def test_endpoint_fleet_401_sin_auth(client, fake_session) -> None:
    resp = await client.get("/api/v1/projects/fleet")
    assert resp.status_code == 401
