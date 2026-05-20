"""Tests B.1 (2026-05-20) — ContentExtractorAgent crea filas Asset.

Antes el agente solo creaba ContentBlock e ignoraba `result.asset_urls`,
`font_urls`, `video_urls` del extractor. Resultado: 0 imágenes
migradas al WP destino. Ahora persiste un `Asset(status=PENDING)` por
cada URL única para que `optimize_assets` las descargue.

Dedupe en dos niveles:
- En memoria por hash (set local) durante el run.
- En BD por UNIQUE(project_id, hash) — el agente pre-carga los hashes
  ya existentes para idempotencia entre runs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_scraper_core.extractors.base import ExtractionResult
from wcm_types.enums import AssetStatus, ScrapeStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.content_extractor import (
    ContentExtractorAgent,
    _normalize_asset_url,
)
from wcm_worker.errors import ContentExtractorError


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 99
    p.builder_source = None
    return p


def _page_mock(*, page_id: int = 1, html: str = "<html><body>x</body></html>") -> MagicMock:
    page = MagicMock()
    page.id = page_id
    page.url = "https://foo.com/"
    page.html_clean = html
    page.lang = "en"
    page.status = ScrapeStatus.SUCCESS
    return page


def _exec_with_pages_and_existing_hashes(
    fake_session: MagicMock,
    *,
    pages: list,
    existing_hashes: list[str],
) -> None:
    """Configura los dos session.execute(): 1º hashes existentes, 2º pages."""
    # 1ª llamada → select(Asset.hash) → scalars().all() == existing_hashes
    res_hashes = MagicMock()
    res_hashes.scalars = MagicMock(
        return_value=MagicMock(all=lambda: existing_hashes)
    )
    # 2ª llamada → select(ScrapedPage) → scalars().all() == pages
    res_pages = MagicMock()
    res_pages.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.side_effect = [res_hashes, res_pages]
    fake_session.get.return_value = _project_mock()


# ---------- helper _normalize_asset_url ----------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://cdn.wixstatic.com/x.png", "https://cdn.wixstatic.com/x.png"),
        ("http://foo.com/y.jpg", "http://foo.com/y.jpg"),
        ("//cdn.example.com/z.webp", "https://cdn.example.com/z.webp"),
        ("  https://foo.com/spaces.png  ", "https://foo.com/spaces.png"),
        # Descartes
        ("", None),
        ("   ", None),
        ("data:image/png;base64,iVBOR...", None),
        ("blob:https://foo.com/abc", None),
        ("javascript:void(0)", None),
        ("mailto:foo@bar.com", None),
        ("tel:+34999", None),
        ("/relative/path.png", None),
        ("relative.jpg", None),
    ],
)
def test_normalize_asset_url(url: str, expected: str | None) -> None:
    assert _normalize_asset_url(url) == expected


# ---------- creación de assets ----------


def test_crea_assets_desde_asset_urls(fake_session) -> None:
    """1 página, 3 URLs únicas → 3 filas Asset PENDING."""
    page = _page_mock()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=[
                "https://cdn.wixstatic.com/img1.png",
                "https://cdn.wixstatic.com/img2.png",
            ],
            font_urls=["https://fonts.googleapis.com/css2?family=Inter"],
            video_urls=[],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    assert result.outputs["assets_created"] == 3
    # session.add fue invocado al menos 3 veces con Asset
    from wcm_db.models.assets import Asset

    asset_calls = [
        c for c in fake_session.add.call_args_list if isinstance(c.args[0], Asset)
    ]
    assert len(asset_calls) == 3
    # Todos PENDING
    for c in asset_calls:
        asset = c.args[0]
        assert asset.status == AssetStatus.PENDING
        assert asset.project_id == 99


def test_dedupe_misma_url_en_dos_paginas(fake_session) -> None:
    """Misma URL en 2 páginas distintas → 1 sola fila Asset."""
    page1 = _page_mock(page_id=1)
    page2 = _page_mock(page_id=2)
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page1, page2], existing_hashes=[]
    )

    shared = ["https://cdn.example.com/logo.png"]
    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=shared,
            font_urls=[],
            video_urls=[],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    assert result.outputs["assets_created"] == 1


def test_no_duplica_si_hash_ya_en_bd(fake_session) -> None:
    """Si el hash ya existe en BD (run previo) → no se crea fila nueva."""
    import hashlib

    page = _page_mock()
    url = "https://cdn.example.com/img.png"
    existing_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[existing_hash]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=[url],
            font_urls=[],
            video_urls=[],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    assert result.outputs["assets_created"] == 0


def test_descarta_urls_invalidas(fake_session) -> None:
    """data:, javascript:, vacíos → ignorados (no cuentan en assets_created)."""
    page = _page_mock()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=[
                "https://valid.com/x.png",
                "data:image/png;base64,iVBOR...",
                "",
                "javascript:void(0)",
                "/relative.jpg",
            ],
            font_urls=[],
            video_urls=[],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    # Solo `https://valid.com/x.png` debe pasar
    assert result.outputs["assets_created"] == 1


def test_protocol_relative_se_normaliza_a_https(fake_session) -> None:
    """`//cdn.example.com/x.png` → `https://cdn.example.com/x.png` en `original_url`."""
    page = _page_mock()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=["//cdn.example.com/x.png"],
            font_urls=[],
            video_urls=[],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    from wcm_db.models.assets import Asset

    assets = [c.args[0] for c in fake_session.add.call_args_list if isinstance(c.args[0], Asset)]
    assert len(assets) == 1
    assert assets[0].original_url == "https://cdn.example.com/x.png"


def test_combinacion_image_font_video(fake_session) -> None:
    """asset_urls + font_urls + video_urls se procesan todas juntas."""
    page = _page_mock()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[],
            asset_urls=["https://x.com/a.png"],
            font_urls=["https://fonts.com/f.woff2"],
            video_urls=["https://v.com/v.mp4"],
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    assert result.outputs["assets_created"] == 3


def test_sin_assets_no_error(fake_session) -> None:
    """Página sin URLs → assets_created=0, sin excepciones."""
    page = _page_mock()
    _exec_with_pages_and_existing_hashes(
        fake_session, pages=[page], existing_hashes=[]
    )

    fake_extractor = MagicMock()
    fake_extractor.extract = MagicMock(
        return_value=ExtractionResult(
            blocks=[], asset_urls=[], font_urls=[], video_urls=[]
        )
    )

    with patch.object(
        ContentExtractorAgent, "_pick_extractor", return_value=fake_extractor
    ):
        result = ContentExtractorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )

    assert result.outputs["assets_created"] == 0


def test_requiere_project_id(fake_session) -> None:
    with pytest.raises(ContentExtractorError, match="project_id"):
        ContentExtractorAgent().run(AgentContext(session=fake_session))
