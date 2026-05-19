"""Tests del endpoint GET /api/v1/projects/{id}/visual-diffs (v0.16.0)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, project_id: int = 1, avg_score: float | None = 0.92) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.visual_diff_avg_score = avg_score
    return p


def _diff_row(*, page_path: str = "/", score: float = 0.95, idx: int = 1) -> MagicMock:
    d = MagicMock()
    d.id = idx
    d.project_id = 1
    d.page_path = page_path
    d.source_screenshot_url = (
        f"https://r2.example/projects/1/visual-diff/{page_path.strip('/') or 'root'}/source.png"
    )
    d.target_screenshot_url = (
        f"https://r2.example/projects/1/visual-diff/{page_path.strip('/') or 'root'}/target.png"
    )
    d.overlay_url = (
        f"https://r2.example/projects/1/visual-diff/{page_path.strip('/') or 'root'}/overlay.png"
    )
    d.score = score
    d.viewport_width = 1280
    now = datetime.now(UTC)
    d.created_at = now
    d.updated_at = now
    return d


@pytest.mark.asyncio
async def test_visual_diffs_404_si_proyecto_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/projects/99/visual-diffs", headers=_auth(viewer_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_visual_diffs_vacio_devuelve_lista_vacia(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock(project_id=1, avg_score=None))
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute = AsyncMock(return_value=result)

    resp = await client.get("/api/v1/projects/1/visual-diffs", headers=_auth(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == 1
    assert body["pages_total"] == 0
    assert body["pages"] == []
    assert body["avg_score"] is None


@pytest.mark.asyncio
async def test_visual_diffs_devuelve_filas_y_avg(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock(avg_score=0.88))
    rows = [
        _diff_row(page_path="/", score=0.95, idx=1),
        _diff_row(page_path="/contacto", score=0.81, idx=2),
    ]
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=lambda: rows))
    fake_session.execute = AsyncMock(return_value=result)

    resp = await client.get("/api/v1/projects/1/visual-diffs", headers=_auth(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["avg_score"] == 0.88
    assert body["pages_total"] == 2
    assert len(body["pages"]) == 2
    paths = {p["page_path"] for p in body["pages"]}
    assert paths == {"/", "/contacto"}


@pytest.mark.asyncio
async def test_visual_diffs_sin_auth_401(client, fake_session) -> None:
    resp = await client.get("/api/v1/projects/1/visual-diffs")
    assert resp.status_code == 401
