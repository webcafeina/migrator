"""Tests del BriefGeneratorAgent (Sprint v0.25.0 Bloque B2).

Mockea OpenAIClient + sesión SQLAlchemy. NO hace llamadas reales.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_types.enums import BlockType, ScrapeStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.brief_generator import BriefGeneratorAgent
from wcm_worker.errors import BriefGeneratorError
from wcm_worker.integrations.openai_client import OpenAIResult


def _project(
    id: int = 42,
    client_name: str = "Mariya Design",
    source_url: str = "https://mariya.design/",
    business_description: str | None = None,
    business_sector: str | None = None,
    tone_of_voice: str | None = None,
    target_audience: str | None = None,
    usps_json: list | None = None,
    nav_items_json: list | None = None,
    theme_styles_origin: dict | None = None,
    builder_source: str = "wix",
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.client_name = client_name
    p.source_url = source_url
    p.business_description = business_description
    p.business_sector = business_sector
    p.tone_of_voice = tone_of_voice
    p.target_audience = target_audience
    p.usps_json = usps_json
    p.nav_items_json = nav_items_json or []
    p.theme_styles_origin = theme_styles_origin or {"colors": {"primary": "#000"}}
    p.builder_source = builder_source
    p.brief_json = None
    return p


def _page(id: int = 1, slug: str = "home", title: str = "Home", depth: int = 0) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.slug = slug
    p.title = title
    p.depth = depth
    p.status = ScrapeStatus.SUCCESS
    return p


def _block(
    *,
    id: int = 1,
    page_id: int = 1,
    project_id: int = 42,
    block_type: BlockType = BlockType.TEXT,
    content_json: dict | None = None,
    order_index: int = 0,
) -> MagicMock:
    b = MagicMock()
    b.id = id
    b.page_id = page_id
    b.project_id = project_id
    b.block_type = block_type
    b.content_json = content_json or {"text": "Bloque ejemplo"}
    b.order_index = order_index
    return b


def _setup_ctx(
    fake_session: MagicMock,
    *,
    project: MagicMock,
    pages: list = None,
    blocks: list = None,
    assets: list = None,
) -> AgentContext:
    fake_session.get.return_value = project
    pages = pages or []
    blocks = blocks or []
    assets = assets or []
    # 3 execute calls: pages, blocks, assets.
    fake_session.execute.side_effect = [
        MagicMock(scalars=lambda: iter(pages)),
        MagicMock(scalars=lambda: iter(blocks)),
        MagicMock(scalars=lambda: iter(assets)),
    ]
    return AgentContext(session=fake_session, project_id=project.id)


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(BriefGeneratorError, match="project_id"):
        BriefGeneratorAgent().run(AgentContext(session=fake_session))


def test_skipped_sin_scraped_pages(fake_session) -> None:
    project = _project()
    ctx = _setup_ctx(fake_session, project=project, pages=[])
    result = BriefGeneratorAgent().run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_scraped_pages"


# ---------- business fields ya seteados (operador editó) ----------


def test_no_invoca_openai_si_campos_business_seteados(fake_session, monkeypatch) -> None:
    """Si business_* están seteados, NO se llama OpenAI."""
    monkeypatch.setenv("OPENAI_API_KEY", "")  # asegurar que from_env devuelve None igualmente
    project = _project(
        business_description="Estudio de joyería de lujo en Madrid.",
        business_sector="portfolio",
        tone_of_voice="premium",
        target_audience="mujeres 35-55",
        usps_json=["Artesanía", "Único"],
    )
    pages = [_page()]
    blocks = [_block()]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)

    mock_client = MagicMock()
    result = BriefGeneratorAgent(openai_client=mock_client).run(ctx)

    # NO se llamó al cliente.
    mock_client.generate_brief_metadata.assert_not_called()
    # Brief generado.
    assert result.outputs["sector"] == "portfolio"
    assert project.brief_json is not None
    assert project.brief_json["business"]["sector"] == "portfolio"


# ---------- auto-detect via OpenAI ----------


def test_auto_detecta_metadata_si_falta_y_openai_disponible(fake_session) -> None:
    """Si business_description vacío + OpenAI configurado → llama OpenAI."""
    project = _project(business_description=None, business_sector=None)
    pages = [_page()]
    blocks = [_block(content_json={"text": "Joyería artesanal"})]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)

    fake_result = OpenAIResult(
        data={
            "business_description": "Joyería artesanal de lujo.",
            "business_sector": "portfolio",
            "tone_of_voice": "premium",
            "target_audience": "mujeres 35-55",
            "usps": ["Hecho a mano", "Diseño único", "Piezas limitadas"],
        },
        tokens_in=500, tokens_out=200, cost_usd=0.001, model="gpt-4o-mini",
    )
    mock_client = MagicMock()
    mock_client.generate_brief_metadata = AsyncMock(return_value=fake_result)

    result = BriefGeneratorAgent(openai_client=mock_client).run(ctx)

    mock_client.generate_brief_metadata.assert_called_once()
    assert project.business_description == "Joyería artesanal de lujo."
    assert project.business_sector == "portfolio"
    assert result.outputs["sector"] == "portfolio"


def test_blocked_si_falta_business_y_sin_openai(fake_session) -> None:
    """Sin OpenAI configurado + faltan campos → marca skipped + warning."""
    project = _project(business_description=None)
    pages = [_page()]
    blocks = [_block()]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)

    # openai_client=None y no env var → from_env devuelve None
    agent = BriefGeneratorAgent(openai_client=None)
    # patcheamos from_env explícitamente para garantizar None
    from unittest.mock import patch
    with patch(
        "wcm_worker.agents.brief_generator.OpenAIClient.from_env",
        return_value=None,
    ):
        result = agent.run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "missing_business_no_openai"
    assert any("OPENAI_API_KEY" in w for w in result.warnings)


# ---------- brief shape ----------


def test_brief_contiene_business_brand_navigation_pages(fake_session) -> None:
    """Smoke test: el Brief tiene las 5 keys top-level esperadas."""
    project = _project(
        business_description="x", business_sector="agency",
        tone_of_voice="friendly", target_audience="x", usps_json=["a"],
        nav_items_json=[{"label": "Home", "url": "/"}],
        theme_styles_origin={"colors": {"primary": "#abc"}, "google_fonts": ["Inter"]},
    )
    pages = [_page(id=1, slug="home", title="Home")]
    blocks = [
        _block(id=1, page_id=1, block_type=BlockType.HERO, content_json={"headline": "Hola"}),
        _block(id=2, page_id=1, block_type=BlockType.NAV, content_json={"menu_items": []}),  # skipped
    ]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)

    BriefGeneratorAgent().run(ctx)
    brief = project.brief_json
    assert set(brief.keys()) == {"business", "brand", "navigation", "footer", "pages"}
    assert brief["business"]["sector"] == "agency"
    assert brief["brand"]["colors"]["primary"] == "#abc"
    assert len(brief["navigation"]) == 1
    assert len(brief["pages"]) == 1
    # NAV block skipped, HERO incluida.
    sections = brief["pages"][0]["sections"]
    assert len(sections) == 1
    assert sections[0]["type"] == "hero"
    assert sections[0]["headline"] == "Hola"


def test_brief_infer_page_intent() -> None:
    agent = BriefGeneratorAgent()
    assert agent._infer_page_intent(_page(slug="home"), []) == "landing"
    assert agent._infer_page_intent(_page(slug=""), []) == "landing"
    assert agent._infer_page_intent(_page(slug="contacto"), []) == "contact"
    assert agent._infer_page_intent(_page(slug="sobre-nosotros"), []) == "about"
    assert agent._infer_page_intent(_page(slug="servicios"), []) == "services"
    assert agent._infer_page_intent(_page(slug="blog"), []) == "blog"
    assert agent._infer_page_intent(_page(slug="aviso-legal"), []) == "legal"
    assert agent._infer_page_intent(_page(slug="extras"), []) == "other"


def test_text_from_block_strip_html() -> None:
    agent = BriefGeneratorAgent()
    block = _block(content_json={"html": "<p>Hola <strong>mundo</strong></p>"})
    text = agent._text_from_block(block)
    assert "Hola" in text
    assert "<p>" not in text
    assert "<strong>" not in text


def test_find_logo_asset_id_por_alt() -> None:
    agent = BriefGeneratorAgent()
    a1 = MagicMock(); a1.id = 1; a1.alt_text = "Foto producto"; a1.original_url = "/x.jpg"
    a2 = MagicMock(); a2.id = 2; a2.alt_text = "Logo empresa"; a2.original_url = "/y.jpg"
    assets = {1: a1, 2: a2}
    assert agent._find_logo_asset_id(assets) == 2


def test_find_logo_asset_id_por_url() -> None:
    agent = BriefGeneratorAgent()
    a1 = MagicMock(); a1.id = 1; a1.alt_text = None; a1.original_url = "https://x.com/logo-empresa.svg"
    assets = {1: a1}
    assert agent._find_logo_asset_id(assets) == 1


def test_find_logo_asset_id_devuelve_none_si_no_match() -> None:
    agent = BriefGeneratorAgent()
    a1 = MagicMock(); a1.id = 1; a1.alt_text = "Foto"; a1.original_url = "/img.jpg"
    assets = {1: a1}
    assert agent._find_logo_asset_id(assets) is None


# ---------- v0.26.0 — design_method por sección ----------


def test_section_design_method_hybrid_hero_es_ai() -> None:
    assert BriefGeneratorAgent._section_design_method("hero", None) == "ai"


def test_section_design_method_hybrid_cta_es_ai() -> None:
    assert BriefGeneratorAgent._section_design_method("cta", None) == "ai"


def test_section_design_method_hybrid_features_es_templates() -> None:
    assert BriefGeneratorAgent._section_design_method("text", None) == "templates"
    assert BriefGeneratorAgent._section_design_method("pricing", None) == "templates"
    assert BriefGeneratorAgent._section_design_method("testimonial", None) == "templates"
    assert BriefGeneratorAgent._section_design_method("gallery", None) == "templates"
    assert BriefGeneratorAgent._section_design_method("form", None) == "templates"


def test_section_design_method_force_templates() -> None:
    """Si project.design_method = templates, fuerza TODOS los tipos a templates."""
    assert BriefGeneratorAgent._section_design_method("hero", "templates") == "templates"
    assert BriefGeneratorAgent._section_design_method("cta", "templates") == "templates"


def test_section_design_method_force_ai() -> None:
    """Si project.design_method = ai, fuerza TODOS los tipos a ai."""
    assert BriefGeneratorAgent._section_design_method("text", "ai") == "ai"
    assert BriefGeneratorAgent._section_design_method("pricing", "ai") == "ai"


def test_brief_pages_sections_incluyen_design_method_en_hybrid(fake_session) -> None:
    """En Hybrid (project.design_method=None), cada sección tiene design_method
    según heurística — hero→ai, text→templates."""
    project = _project(
        business_description="Estudio creativo",
        business_sector="agency",
        tone_of_voice="friendly",
        target_audience="PYMEs",
        usps_json=["Único"],
    )
    project.design_method = None  # Hybrid
    pages = [_page()]
    blocks = [
        _block(id=1, block_type=BlockType.HERO, content_json={"headline": "Hola"}),
        _block(id=2, block_type=BlockType.TEXT, content_json={"html": "<p>x</p>"}),
        _block(id=3, block_type=BlockType.CTA, content_json={"cta_text": "Contacta"}),
    ]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)
    BriefGeneratorAgent().run(ctx)
    sections = project.brief_json["pages"][0]["sections"]
    by_type = {s["type"]: s["design_method"] for s in sections}
    assert by_type["hero"] == "ai"
    assert by_type["text"] == "templates"
    assert by_type["cta"] == "ai"


def test_brief_pages_sections_force_templates_si_project_design_method_templates(fake_session) -> None:
    project = _project(
        business_description="x", business_sector="agency",
        tone_of_voice="friendly", target_audience="x", usps_json=["x"],
    )
    project.design_method = "templates"
    pages = [_page()]
    blocks = [
        _block(id=1, block_type=BlockType.HERO, content_json={"headline": "Hola"}),
        _block(id=2, block_type=BlockType.CTA, content_json={"cta_text": "x"}),
    ]
    ctx = _setup_ctx(fake_session, project=project, pages=pages, blocks=blocks)
    BriefGeneratorAgent().run(ctx)
    sections = project.brief_json["pages"][0]["sections"]
    for s in sections:
        assert s["design_method"] == "templates"
