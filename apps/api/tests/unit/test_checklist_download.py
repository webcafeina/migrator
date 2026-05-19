"""Tests del endpoint GET /api/v1/projects/{id}/checklist/download (v0.16.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(
    *,
    project_id: int = 1,
    md_url: str | None = None,
    pdf_url: str | None = None,
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.checklist_md_url = md_url
    p.checklist_pdf_url = pdf_url
    return p


@pytest.mark.asyncio
async def test_404_si_proyecto_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/projects/99/checklist/download", headers=_auth(viewer_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_404_si_checklist_no_generado(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock(pdf_url=None))
    resp = await client.get(
        "/api/v1/projects/1/checklist/download?format=pdf",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_redirect_si_url_https(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(
        return_value=_project_mock(pdf_url="https://r2.example/projects/1/checklist.pdf")
    )
    resp = await client.get(
        "/api/v1/projects/1/checklist/download?format=pdf",
        headers=_auth(viewer_token),
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://r2.example/projects/1/checklist.pdf"


@pytest.mark.asyncio
async def test_stream_si_url_file(client, fake_session, viewer_token, tmp_path) -> None:
    pdf_path = tmp_path / "checklist.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake pdf content")
    fake_session.get = AsyncMock(return_value=_project_mock(pdf_url=f"file://{pdf_path}"))
    resp = await client.get(
        "/api/v1/projects/1/checklist/download?format=pdf",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_format_md_devuelve_md(client, fake_session, viewer_token, tmp_path) -> None:
    md_path = tmp_path / "checklist.md"
    md_path.write_bytes(b"# checklist\n\nDemo content.")
    fake_session.get = AsyncMock(return_value=_project_mock(md_url=f"file://{md_path}"))
    resp = await client.get(
        "/api/v1/projects/1/checklist/download?format=md",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 200
    assert "markdown" in resp.headers["content-type"]
    assert resp.content == b"# checklist\n\nDemo content."


@pytest.mark.asyncio
async def test_format_invalido_422(client, fake_session, viewer_token) -> None:
    resp = await client.get(
        "/api/v1/projects/1/checklist/download?format=docx",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sin_auth_401(client, fake_session) -> None:
    resp = await client.get("/api/v1/projects/1/checklist/download")
    assert resp.status_code == 401
