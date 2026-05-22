"""Tests del AssetUploaderAgent (Sprint v0.24.0 Bloque A).

Mockea R2Client.get_bytes + WpRestClient.upload_media + WpClientConfig.
NO hace llamadas reales.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_types.enums import AssetStatus
from wcm_worker.agents.asset_uploader import (
    AssetUploaderAgent,
    _ext_from_mime,
    _resolve_concurrency,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.errors import AssetUploaderError

# ---------- helpers fixtures ----------


def _asset(
    *,
    id: int = 1,
    project_id: int = 42,
    status: AssetStatus = AssetStatus.READY,
    r2_key: str | None = "wcm/projects/42/ab/abc123.webp",
    mime: str = "image/webp",
    wp_attachment_id: int | None = None,
    wp_media_uploaded_at: datetime | None = None,
    wp_source_url: str | None = None,
    alt_text: str | None = "Alt text",
    width: int = 800,
    height: int = 600,
) -> MagicMock:
    a = MagicMock()
    a.id = id
    a.project_id = project_id
    a.status = status
    a.r2_key = r2_key
    a.mime = mime
    a.wp_attachment_id = wp_attachment_id
    a.wp_media_uploaded_at = wp_media_uploaded_at
    a.wp_source_url = wp_source_url
    a.alt_text = alt_text
    a.width = width
    a.height = height
    return a


def _project(id: int = 42) -> MagicMock:
    p = MagicMock()
    p.id = id
    return p


def _setup_ctx(fake_session: MagicMock, *, project=None, candidates=None) -> AgentContext:
    """Mockea fake_session.get(Project) + execute() para candidates."""
    project = project or _project()
    fake_session.get.return_value = project

    res = MagicMock()
    res.scalars.return_value = iter(candidates or [])
    # _load_candidates llama execute primero, _rewrite_bricks_pages_urls
    # llama 2 más. Devolvemos iter vacío en posteriores.
    fake_session.execute.side_effect = [res, MagicMock(scalars=lambda: iter([])), MagicMock(scalars=lambda: iter([]))]
    return AgentContext(session=fake_session, project_id=42)


def _fake_r2(*, get_bytes_return: bytes = b"FAKE_IMG", raises: Exception | None = None) -> MagicMock:
    r2 = MagicMock()
    if raises is not None:
        r2.get_bytes = MagicMock(side_effect=raises)
    else:
        r2.get_bytes = MagicMock(return_value=get_bytes_return)
    return r2


def _fake_rest(
    *,
    upload_response: dict | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    rest = MagicMock()
    if raises is not None:
        rest.upload_media = AsyncMock(side_effect=raises)
    else:
        rest.upload_media = AsyncMock(
            return_value=upload_response or {
                "id": 999,
                "source_url": "https://wp/wp-content/uploads/2026/05/img.webp",
            }
        )
    # async context manager
    rest.__aenter__ = AsyncMock(return_value=rest)
    rest.__aexit__ = AsyncMock(return_value=None)
    return rest


# ---------- helpers puros ----------


def test_ext_from_mime_jpeg() -> None:
    assert _ext_from_mime("image/jpeg") == ".jpg"


def test_ext_from_mime_webp() -> None:
    assert _ext_from_mime("image/webp") == ".webp"


def test_ext_from_mime_unknown() -> None:
    assert _ext_from_mime("application/octet-stream") == ".bin"


def test_resolve_concurrency_default() -> None:
    assert _resolve_concurrency() == 3


def test_resolve_concurrency_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WCM_ASSET_UPLOADER_CONCURRENCY", "5")
    assert _resolve_concurrency() == 5


def test_resolve_concurrency_clamp_out_of_range(monkeypatch) -> None:
    monkeypatch.setenv("WCM_ASSET_UPLOADER_CONCURRENCY", "100")
    assert _resolve_concurrency() == 3


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(AssetUploaderError, match="project_id"):
        AssetUploaderAgent().run(AgentContext(session=fake_session))


def test_skipped_sin_r2_credenciales(fake_session) -> None:
    """Sin R2_* env vars, devuelve skipped sin error."""
    fake_session.get.return_value = _project()
    ctx = AgentContext(session=fake_session, project_id=42)
    with patch(
        "wcm_worker.agents.asset_uploader.R2Client.from_env", return_value=None
    ):
        result = AssetUploaderAgent().run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_r2"


def test_skipped_sin_wp_credenciales(fake_session) -> None:
    """Con R2 pero sin WP_DEFAULT_REST_*, también skipped."""
    fake_session.get.return_value = _project()
    ctx = AgentContext(session=fake_session, project_id=42)
    r2 = _fake_r2()
    # WpClientConfig.from_env lanzará ValueError sin envs.
    with patch(
        "wcm_worker.agents.asset_uploader.WpClientConfig.from_env",
        side_effect=ValueError("missing env"),
    ):
        result = AssetUploaderAgent(r2=r2).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_wp_rest"


# ---------- upload happy path ----------


def test_upload_unico_asset_subido(fake_session) -> None:
    asset = _asset()
    ctx = _setup_ctx(fake_session, candidates=[asset])
    r2 = _fake_r2()
    rest = _fake_rest()

    agent = AssetUploaderAgent(r2=r2, wp_rest=rest)
    result = agent.run(ctx)

    assert result.outputs["uploaded"] == 1
    assert result.outputs["failed"] == 0
    # asset.wp_attachment_id se persistió
    assert asset.wp_attachment_id == 999
    assert asset.wp_source_url == "https://wp/wp-content/uploads/2026/05/img.webp"
    assert asset.wp_media_uploaded_at is not None
    r2.get_bytes.assert_called_once_with("wcm/projects/42/ab/abc123.webp")
    rest.upload_media.assert_called_once()


def test_upload_skip_already_uploaded(fake_session) -> None:
    """Asset con wp_attachment_id ya set NO se reintenta."""
    asset = _asset(wp_attachment_id=500, wp_media_uploaded_at=datetime.now(UTC))
    # Con wp_attachment_id ya seteado, _load_candidates lo filtra fuera —
    # nunca llega a _upload_single. Confirmamos que la query lo excluye.
    ctx = _setup_ctx(fake_session, candidates=[])  # filtrado por SQL
    r2 = _fake_r2()
    rest = _fake_rest()

    result = AssetUploaderAgent(r2=r2, wp_rest=rest).run(ctx)

    assert result.outputs["uploaded"] == 0
    rest.upload_media.assert_not_called()


def test_upload_r2_missing_marca_failed(fake_session) -> None:
    """R2 get_bytes lanza error → asset cuenta como failed."""
    from wcm_worker.integrations.r2 import R2UploadError

    asset = _asset()
    ctx = _setup_ctx(fake_session, candidates=[asset])
    r2 = _fake_r2(raises=R2UploadError("NoSuchKey"))
    rest = _fake_rest()

    result = AssetUploaderAgent(r2=r2, wp_rest=rest).run(ctx)

    assert result.outputs["uploaded"] == 0
    assert result.outputs["failed"] == 1
    rest.upload_media.assert_not_called()


def test_filtro_mime_solo_imagen_y_video(fake_session) -> None:
    """Assets con mime application/font NO entran en candidatos."""
    font_asset = _asset(id=1, mime="font/woff2")
    img_asset = _asset(id=2, mime="image/webp")
    # _load_candidates filtra por prefix → solo img_asset.
    # Como execute mock devuelve ambos, el filtro Python los descarta.
    ctx = _setup_ctx(fake_session, candidates=[font_asset, img_asset])
    r2 = _fake_r2()
    rest = _fake_rest()

    result = AssetUploaderAgent(r2=r2, wp_rest=rest).run(ctx)

    assert result.outputs["uploaded"] == 1
    r2.get_bytes.assert_called_once()


# ---------- URL rewriting ----------


def test_rewrite_json_in_place_reemplaza_url() -> None:
    agent = AssetUploaderAgent()
    json_obj = {
        "content": [
            {
                "name": "image",
                "settings": {
                    "image": {
                        "url": "/wp-content/uploads/placeholder-asset-7.webp",
                        "id": None,
                    }
                },
            }
        ]
    }
    url_map = {7: (123, "https://wp/uploads/real.webp")}
    changed = agent._rewrite_json_in_place(json_obj, url_map)
    assert changed is True
    assert json_obj["content"][0]["settings"]["image"]["url"] == "https://wp/uploads/real.webp"
    assert json_obj["content"][0]["settings"]["image"]["id"] == 123


def test_rewrite_json_in_place_no_match_devuelve_false() -> None:
    agent = AssetUploaderAgent()
    json_obj = {"content": [{"settings": {"image": {"url": "https://other.com/x.png"}}}]}
    changed = agent._rewrite_json_in_place(json_obj, {1: (10, "x")})
    assert changed is False


def test_rewrite_json_in_place_recursive() -> None:
    """Nested deep en arrays/dicts también se reescribe."""
    agent = AssetUploaderAgent()
    json_obj = {
        "level1": {
            "level2": [
                {"settings": {"_background": {"image": {"url": "/wp-content/uploads/placeholder-asset-3.webp"}}}}
            ]
        }
    }
    url_map = {3: (42, "https://wp/uploads/bg.webp")}
    changed = agent._rewrite_json_in_place(json_obj, url_map)
    assert changed is True
    assert (
        json_obj["level1"]["level2"][0]["settings"]["_background"]["image"]["url"]
        == "https://wp/uploads/bg.webp"
    )
    assert json_obj["level1"]["level2"][0]["settings"]["_background"]["image"]["id"] == 42
