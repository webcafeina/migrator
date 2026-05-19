"""Tests del endpoint GET /api/v1/projects/{id}/qa-report (v0.16.0)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_id: int = 1) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    return p


def _qa_report(**over) -> MagicMock:
    r = MagicMock()
    r.id = 1
    r.project_id = 1
    r.lighthouse_perf_desktop = 85
    r.lighthouse_perf_mobile = 72
    r.lighthouse_a11y_avg = 90
    r.lighthouse_best_practices_avg = 92
    r.lighthouse_seo_avg = 100
    r.html_validator_errors_count = 0
    r.html_validator_warnings_count = 5
    r.broken_links_count = 0
    r.total_links_checked = 42
    r.https_valid = True
    r.robots_accessible = True
    r.sitemap_accessible = True
    r.report_json = {"lighthouse_skipped": False, "broken_links": []}
    now = datetime.now(UTC)
    r.created_at = now
    r.updated_at = now
    for k, v in over.items():
        setattr(r, k, v)
    return r


@pytest.mark.asyncio
async def test_qa_report_404_si_proyecto_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/projects/99/qa-report", headers=_auth(viewer_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_qa_report_null_si_nunca_ejecutado(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session.execute = AsyncMock(return_value=result)

    resp = await client.get("/api/v1/projects/1/qa-report", headers=_auth(viewer_token))
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_qa_report_devuelve_ultima_ejecucion(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock())
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=_qa_report())
    fake_session.execute = AsyncMock(return_value=result)

    resp = await client.get("/api/v1/projects/1/qa-report", headers=_auth(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["lighthouse_perf_desktop"] == 85
    assert body["lighthouse_perf_mobile"] == 72
    assert body["https_valid"] is True
    assert body["broken_links_count"] == 0


@pytest.mark.asyncio
async def test_qa_report_sin_auth_401(client, fake_session) -> None:
    resp = await client.get("/api/v1/projects/1/qa-report")
    assert resp.status_code == 401
