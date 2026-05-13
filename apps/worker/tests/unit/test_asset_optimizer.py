"""Tests del AssetOptimizerAgent."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import httpx
import pytest

from wcm_types.enums import AssetStatus
from wcm_worker.agents.asset_optimizer import (
    AssetOptimizerAgent,
    _ext_for_mime,
    _sniff_mime,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.errors import AssetOptimizerError


def _png_bytes(width: int = 16, height: int = 16) -> bytes:
    """Genera un PNG válido pequeño para tests sin tocar disco."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(180, 220, 0))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _asset_mock(*, id_: int = 1, status=AssetStatus.PENDING) -> MagicMock:
    a = MagicMock()
    a.id = id_
    a.project_id = 42
    a.original_url = "https://example.com/img.png"
    a.status = status
    a.hash = "old-hash"
    a.error_message = None
    a.mime = None
    a.size_bytes = None
    a.width = None
    a.height = None
    a.r2_key = None
    a.optimized_path = None
    return a


def _ctx(fake_session, assets) -> AgentContext:
    scalars = MagicMock()
    scalars.__iter__ = lambda self: iter(assets)
    res = MagicMock()
    res.scalars.return_value = scalars
    fake_session.execute.return_value = res
    return AgentContext(session=fake_session, project_id=42)


def test_optimizer_requires_project_id(fake_session) -> None:
    with pytest.raises(AssetOptimizerError, match="project_id"):
        AssetOptimizerAgent(http_client=httpx.Client()).run(
            AgentContext(session=fake_session)
        )


def test_optimizer_no_pending_assets(fake_session) -> None:
    ctx = _ctx(fake_session, [])
    result = AssetOptimizerAgent(http_client=httpx.Client()).run(ctx)
    assert result.outputs == {"processed": 0}


def test_optimizer_converts_png_to_webp_and_uploads(fake_session) -> None:
    asset = _asset_mock()
    png_data = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png_data)

    http = httpx.Client(transport=httpx.MockTransport(handler))

    fake_r2 = MagicMock()
    fake_r2.put_bytes.return_value = "https://cdn/x.webp"

    ctx = _ctx(fake_session, [asset])
    result = AssetOptimizerAgent(r2=fake_r2, http_client=http).run(ctx)

    assert asset.status == AssetStatus.READY
    assert asset.mime == "image/webp"
    assert asset.r2_key is not None
    assert asset.r2_key.startswith("wcm/projects/42/")
    assert asset.r2_key.endswith(".webp")
    assert asset.width == 16
    assert asset.height == 16
    assert result.outputs["optimized"] == 1
    assert result.outputs["uploaded"] == 1


def test_optimizer_no_r2_leaves_asset_optimized_not_ready(fake_session, monkeypatch) -> None:
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    asset = _asset_mock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_png_bytes())

    http = httpx.Client(transport=httpx.MockTransport(handler))

    ctx = _ctx(fake_session, [asset])
    result = AssetOptimizerAgent(http_client=http).run(ctx)

    assert asset.status == AssetStatus.OPTIMIZED
    assert asset.r2_key is None
    assert result.outputs["uploaded"] == 0
    assert result.outputs["optimized"] == 1
    assert result.outputs["r2_configured"] is False


def test_optimizer_download_failure_marks_failed(fake_session) -> None:
    asset = _asset_mock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ctx = _ctx(fake_session, [asset])
    result = AssetOptimizerAgent(http_client=http).run(ctx)

    assert asset.status == AssetStatus.PENDING
    assert "HTTP 404" in asset.error_message
    assert result.outputs["failed"] == 1


def test_optimizer_oversize_rejected(fake_session) -> None:
    asset = _asset_mock()
    huge = b"x" * (9 * 1024 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=huge)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ctx = _ctx(fake_session, [asset])
    result = AssetOptimizerAgent(http_client=http).run(ctx)
    assert result.outputs["failed"] == 1


def test_sniff_mime_recognizes_common_formats() -> None:
    assert _sniff_mime(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16) == "image/png"
    assert _sniff_mime(b"\xff\xd8\xff" + b"\x00" * 16) == "image/jpeg"
    assert _sniff_mime(b"GIF89a" + b"\x00" * 16) == "image/gif"
    assert _sniff_mime(b"RIFF\x00\x00\x00\x00WEBPxxxx") == "image/webp"
    assert _sniff_mime(b"%PDF" + b"\x00" * 16) == "application/pdf"
    assert _sniff_mime(b"xxxxxxxxxxxx") is None


def test_ext_for_mime_default_bin() -> None:
    assert _ext_for_mime("image/webp") == ".webp"
    assert _ext_for_mime("application/unknown") == ".bin"
