"""Tests del AssetOptimizerAgent."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

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

    # B.8 — download failed → status FAILED (antes era PENDING, lo que
    # producía retries infinitos del mismo asset roto).
    assert asset.status == AssetStatus.FAILED
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


# B.8 — dedup por content_hash. Si dos URLs distintas devuelven el
# mismo binario, el segundo asset se marca READY reusando el r2_key
# del primero, sin volver a subir.


def _ctx_with_two_executes(
    fake_session: MagicMock,
    *,
    existing_ready_assets: list,
    pending_assets: list,
) -> AgentContext:
    """Patrón B.8: el agente hace dos SELECT — primero existing READY
    (para construir el dedup dict), luego pending."""
    res_existing = MagicMock()
    res_existing.scalars.return_value = MagicMock(
        __iter__=lambda self: iter(existing_ready_assets)
    )
    res_pending = MagicMock()
    res_pending.scalars.return_value = MagicMock(
        __iter__=lambda self: iter(pending_assets)
    )
    fake_session.execute.side_effect = [res_existing, res_pending]
    return AgentContext(session=fake_session, project_id=42)


def test_dedup_segundo_asset_reusa_r2_key_del_primero(fake_session) -> None:
    """Dos assets con URLs distintas pero mismo binario → el 2º se
    marca READY reusando r2_key/optimized_path del 1º, sin volver a
    subir a R2 ni chocar el UNIQUE(project_id, hash)."""
    png_data = _png_bytes()
    asset1 = _asset_mock(id_=1)
    asset1.original_url = "https://cdn.wixstatic.com/u1.png?v=1"
    asset2 = _asset_mock(id_=2)
    asset2.original_url = "https://cdn.wixstatic.com/u1.png?v=2"  # mismo content

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png_data)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    fake_r2 = MagicMock()
    fake_r2.put_bytes.return_value = "https://cdn/x.webp"

    ctx = _ctx_with_two_executes(
        fake_session, existing_ready_assets=[], pending_assets=[asset1, asset2]
    )
    result = AssetOptimizerAgent(http_client=http, r2=fake_r2).run(ctx)

    assert result.outputs["uploaded"] == 1
    assert result.outputs["deduplicated"] == 1
    # R2 solo se invocó UNA vez (el 2º se reusa)
    assert fake_r2.put_bytes.call_count == 1
    # Ambos terminan READY
    assert asset1.status == AssetStatus.READY
    assert asset2.status == AssetStatus.READY
    # El r2_key del 2º apunta al mismo path del 1º
    assert asset2.r2_key == asset1.r2_key
    assert asset2.optimized_path == asset1.optimized_path
    # CRÍTICO: el hash del 2º NO se sobrescribe con content_hash. Mantiene
    # el placeholder original para no chocar el UNIQUE(project_id, hash).
    assert asset2.hash == "old-hash"
    # El 1º sí lleva el content_hash real (sha256 de los bytes WebP).
    assert asset1.hash != "old-hash"
    assert len(asset1.hash) == 64  # hex sha256


def test_dedup_contra_run_previo_no_resube(fake_session) -> None:
    """Run anterior dejó un asset READY con content_hash X. Run actual
    procesa otra URL cuyo binario también es X → se dedupea contra el
    asset histórico."""
    import hashlib

    from PIL import Image

    png_data = _png_bytes()
    # Computamos content_hash que el optimizer obtendrá tras WebP conversion
    img = Image.open(io.BytesIO(png_data))
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=82, method=4)
    content_hash = hashlib.sha256(out.getvalue()).hexdigest()

    previous_asset = _asset_mock(id_=99)
    previous_asset.hash = content_hash
    previous_asset.status = AssetStatus.READY
    previous_asset.r2_key = "wcm/projects/42/aa/aa.webp"
    previous_asset.optimized_path = "wcm/projects/42/aa/aa.webp"
    previous_asset.mime = "image/webp"
    previous_asset.size_bytes = 1234
    previous_asset.width = 100
    previous_asset.height = 100

    new_asset = _asset_mock(id_=1)
    new_asset.original_url = "https://cdn/other-url.png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png_data)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    fake_r2 = MagicMock()

    ctx = _ctx_with_two_executes(
        fake_session,
        existing_ready_assets=[previous_asset],
        pending_assets=[new_asset],
    )
    result = AssetOptimizerAgent(http_client=http, r2=fake_r2).run(ctx)

    # NO se subió nada nuevo a R2.
    assert fake_r2.put_bytes.call_count == 0
    assert result.outputs["uploaded"] == 0
    assert result.outputs["deduplicated"] == 1
    assert new_asset.status == AssetStatus.READY
    assert new_asset.r2_key == "wcm/projects/42/aa/aa.webp"


def test_dedup_no_dispara_si_content_distinto(fake_session) -> None:
    """Si dos URLs devuelven binarios distintos, ambos suben a R2."""
    png1 = _png_bytes(width=10, height=10)
    png2 = _png_bytes(width=20, height=20)
    asset1 = _asset_mock(id_=1)
    asset1.original_url = "https://x.com/a.png"
    asset2 = _asset_mock(id_=2)
    asset2.original_url = "https://x.com/b.png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png1 if "a.png" in str(request.url) else png2)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    fake_r2 = MagicMock()
    fake_r2.put_bytes.return_value = "https://cdn/x.webp"

    ctx = _ctx_with_two_executes(
        fake_session, existing_ready_assets=[], pending_assets=[asset1, asset2]
    )
    result = AssetOptimizerAgent(http_client=http, r2=fake_r2).run(ctx)

    assert result.outputs["uploaded"] == 2
    assert result.outputs["deduplicated"] == 0
    assert fake_r2.put_bytes.call_count == 2


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
