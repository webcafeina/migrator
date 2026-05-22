"""Tests del PreviewThumbnailsAgent (Sprint v0.26.0 B6).

Mockea el screenshotter Playwright + sesión SQLAlchemy. NO lanza Chromium.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.preview_thumbnails import PreviewThumbnailsAgent
from wcm_worker.errors import RedesignAgentError


def _project(*, id: int = 42) -> MagicMock:
    p = MagicMock()
    p.id = id
    return p


def _bricks_page(
    *,
    id: int = 1,
    slug: str = "home",
    wp_post_id: int | None = 101,
    project_id: int = 42,
) -> MagicMock:
    bp = MagicMock()
    bp.id = id
    bp.slug = slug
    bp.wp_post_id = wp_post_id
    bp.project_id = project_id
    bp.preview_thumbnail_url = None
    bp.preview_captured_at = None
    return bp


def _ctx(fake_session, project, pages):
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalars.return_value.all.return_value = pages
    return AgentContext(session=fake_session, project_id=project.id)


@pytest.fixture
def wp_env(monkeypatch):
    monkeypatch.setenv("WP_DEFAULT_SITE_URL", "https://staging.example.com")
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "admin")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "abcd efgh ijkl")


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(RedesignAgentError, match="project_id"):
        PreviewThumbnailsAgent().run(AgentContext(session=fake_session))


def test_skipped_si_no_hay_paginas_deployadas(fake_session, wp_env) -> None:
    project = _project()
    ctx = _ctx(fake_session, project, pages=[])
    result = PreviewThumbnailsAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_deployed_pages"


def test_skipped_si_no_hay_wp_target_configurado(fake_session, monkeypatch) -> None:
    monkeypatch.delenv("WP_DEFAULT_SITE_URL", raising=False)
    project = _project()
    ctx = _ctx(fake_session, project, pages=[_bricks_page()])
    result = PreviewThumbnailsAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_wp_target"


# ---------- captura ----------


def test_captura_screenshot_y_actualiza_bricks_page(
    fake_session, wp_env, tmp_path
) -> None:
    project = _project()
    bp = _bricks_page(slug="home", wp_post_id=101)
    ctx = _ctx(fake_session, project, pages=[bp])

    screenshotter = AsyncMock(return_value=b"\x89PNG\r\nfake-bytes")
    agent = PreviewThumbnailsAgent(
        screenshotter=screenshotter, output_dir=tmp_path,
    )
    result = agent.run(ctx)

    # Llamó al screenshotter con la URL preview correcta.
    assert screenshotter.call_count == 1
    url_called, target_called = screenshotter.call_args.args
    assert url_called == "https://staging.example.com/?p=101&preview=true"
    assert target_called["user"] == "admin"
    assert target_called["app_password"] == "abcdefghijkl"  # spaces removed

    # Persistió el PNG localmente y actualizó el bricks_page.
    assert bp.preview_thumbnail_url is not None
    assert bp.preview_thumbnail_url.startswith("file://")
    assert bp.preview_captured_at is not None

    # PNG escrito a disco.
    expected_path = tmp_path / "projects/42/previews/home.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"\x89PNG\r\nfake-bytes"

    # Output summary.
    assert result.outputs["captured"] == 1
    assert result.outputs["failed"] == 0


def test_usa_uploader_si_inyectado(fake_session, wp_env, tmp_path) -> None:
    project = _project()
    bp = _bricks_page(slug="contacto", wp_post_id=42)
    ctx = _ctx(fake_session, project, pages=[bp])

    captured_uploads: list[tuple[str, bytes]] = []

    def fake_uploader(key: str, data: bytes) -> str:
        captured_uploads.append((key, data))
        return f"https://r2.example.com/{key}"

    screenshotter = AsyncMock(return_value=b"\x89PNG\r\n")
    agent = PreviewThumbnailsAgent(
        screenshotter=screenshotter, uploader=fake_uploader,
        output_dir=tmp_path,
    )
    agent.run(ctx)

    assert len(captured_uploads) == 1
    key, data = captured_uploads[0]
    assert key == "projects/42/previews/contacto.png"
    assert data == b"\x89PNG\r\n"
    assert bp.preview_thumbnail_url == (
        "https://r2.example.com/projects/42/previews/contacto.png"
    )


def test_screenshot_falla_emite_residual_y_continua(
    fake_session, wp_env, tmp_path
) -> None:
    """Si una página falla, residual + warning, sigue con las demás."""
    project = _project()
    bp1 = _bricks_page(slug="home", wp_post_id=1)
    bp2 = _bricks_page(slug="about", wp_post_id=2)
    ctx = _ctx(fake_session, project, pages=[bp1, bp2])

    # 1ª llamada falla, 2ª OK.
    screenshotter = AsyncMock(
        side_effect=[Exception("timeout"), b"PNG"],
    )
    added: list = []
    fake_session.add.side_effect = lambda obj: added.append(obj)

    agent = PreviewThumbnailsAgent(
        screenshotter=screenshotter, output_dir=tmp_path,
    )
    result = agent.run(ctx)

    assert result.outputs["captured"] == 1
    assert result.outputs["failed"] == 1
    # ResidualTask creado para bp1.
    assert any(
        getattr(o, "generated_by", None) == "preview_thumbnails" for o in added
    )


# ---------- helpers estáticos ----------


def test_preview_url_format() -> None:
    url = PreviewThumbnailsAgent._preview_url(
        "https://staging.example.com", 123
    )
    assert url == "https://staging.example.com/?p=123&preview=true"


def test_resolve_wp_target_lee_envs(monkeypatch) -> None:
    monkeypatch.setenv("WP_DEFAULT_SITE_URL", "https://x.com/")
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "u")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "a b c d")
    target = PreviewThumbnailsAgent._resolve_wp_target(MagicMock())
    assert target == {
        "site_url": "https://x.com",  # trailing slash stripped
        "user": "u",
        "app_password": "abcd",  # spaces stripped
    }


def test_resolve_wp_target_devuelve_none_si_falta(monkeypatch) -> None:
    monkeypatch.delenv("WP_DEFAULT_SITE_URL", raising=False)
    monkeypatch.setenv("WP_DEFAULT_REST_USER", "u")
    monkeypatch.setenv("WP_DEFAULT_REST_APP_PASSWORD", "p")
    assert PreviewThumbnailsAgent._resolve_wp_target(MagicMock()) is None
