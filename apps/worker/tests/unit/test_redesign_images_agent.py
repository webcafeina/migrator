"""Tests del RedesignImagesAgent (Sprint v0.26.0 B5).

Mockea OpenAIClient.generate_image + sesión SQLAlchemy. NO hace llamadas
reales a OpenAI ni R2.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.redesign_images import (
    _IMAGE_SECTION_TYPES,
    RedesignImagesAgent,
)
from wcm_worker.errors import OpenAIClientError, RedesignAgentError
from wcm_worker.integrations.openai_client import OpenAIImageResult


def _project(
    *,
    id: int = 42,
    brief_json: dict | None = None,
    budget: Decimal | float | None = None,
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.brief_json = brief_json
    p.image_generation_budget_usd = budget
    return p


def _ctx(fake_session, project) -> AgentContext:
    fake_session.get.return_value = project
    # Asset.flush() asigna un id mock determinístico.
    next_asset_id = [100]

    def _on_add(obj):
        if hasattr(obj, "hash") and not getattr(obj, "id", None):
            obj.id = next_asset_id[0]
            next_asset_id[0] += 1

    fake_session.add.side_effect = _on_add
    return AgentContext(session=fake_session, project_id=project.id)


def _brief_with_empty_hero() -> dict:
    return {
        "business": {
            "name": "Acme",
            "description": "Estudio creativo",
            "sector": "agency",
            "tone_of_voice": "premium",
        },
        "brand": {"colors": {"primary": "#000", "secondary": "#fff"}, "fonts": {}},
        "pages": [
            {
                "slug": "home",
                "title": "Home",
                "intent": "landing",
                "sections": [
                    {"type": "hero", "design_method": "ai", "headline": "Bienvenido"},
                    {"type": "text", "design_method": "templates", "html": "<p>x</p>"},
                ],
            }
        ],
    }


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(RedesignAgentError, match="project_id"):
        RedesignImagesAgent().run(AgentContext(session=fake_session))


def test_skipped_sin_brief(fake_session) -> None:
    project = _project(brief_json=None)
    ctx = _ctx(fake_session, project)
    result = RedesignImagesAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_brief"


def test_skipped_sin_slots_vacios(fake_session) -> None:
    """Brief con todos los slots de imagen rellenos → SKIPPED."""
    brief = _brief_with_empty_hero()
    # Rellenar el slot de imagen del hero.
    brief["pages"][0]["sections"][0]["asset_id"] = 999
    project = _project(brief_json=brief)
    ctx = _ctx(fake_session, project)
    result = RedesignImagesAgent().run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_empty_slots"


def test_skipped_sin_openai_key(fake_session, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    project = _project(brief_json=_brief_with_empty_hero())
    ctx = _ctx(fake_session, project)
    result = RedesignImagesAgent().run(ctx)  # client=None → from_env devuelve None
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_openai_key"


# ---------- generación normal ----------


def test_genera_imagen_para_hero_vacio(fake_session) -> None:
    """Brief con hero sin asset_id → gpt-image-2 genera → asset_id se
    inyecta + ai_image_metadata se adjunta."""
    project = _project(brief_json=_brief_with_empty_hero())
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_image = AsyncMock(
        return_value=OpenAIImageResult(
            image_bytes=b"\x89PNG\r\nfake",
            mime="image/png",
            width=1536,
            height=1024,
            cost_usd=0.041,
            model="gpt-image-2",
            quality="medium",
            size="1536x1024",
            prompt="prompt deterministic",
        )
    )

    result = RedesignImagesAgent(openai_client=client).run(ctx)

    assert client.generate_image.call_count == 1
    assert result.outputs["images_generated"] == 1
    assert result.outputs["images_failed"] == 0
    assert abs(result.outputs["cost_usd_total"] - 0.041) < 1e-9
    # Sección del Brief actualizada en place.
    hero = project.brief_json["pages"][0]["sections"][0]
    assert hero["asset_id"] == 100
    meta = hero["ai_image_metadata"]
    assert meta["model"] == "gpt-image-2"
    assert meta["quality"] == "medium"
    assert abs(meta["cost_usd"] - 0.041) < 1e-9


def test_omite_secciones_con_asset_existente(fake_session) -> None:
    """Slots con asset_id ya seteado se omiten (no se llama OpenAI)."""
    brief = _brief_with_empty_hero()
    brief["pages"][0]["sections"].append(
        {"type": "image", "design_method": "templates", "asset_id": 7}
    )
    project = _project(brief_json=brief)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_image = AsyncMock(
        return_value=OpenAIImageResult(
            image_bytes=b"x", mime="image/png", width=1024, height=1024,
            cost_usd=0.053, model="gpt-image-2", quality="medium",
            size="1024x1024", prompt="p",
        )
    )
    result = RedesignImagesAgent(openai_client=client).run(ctx)
    # Solo se generó para el hero (1 slot), no para image (asset_id ya
    # presente).
    assert client.generate_image.call_count == 1
    assert result.outputs["slots_total"] == 1


def test_omite_tipos_sin_imagen(fake_session) -> None:
    """text/faq/pricing/form/cta sin asset_id no se procesan."""
    brief = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [{
            "slug": "home", "title": "H", "intent": "landing",
            "sections": [
                {"type": "text", "html": "<p>x</p>"},
                {"type": "faq", "items": []},
                {"type": "pricing", "tiers": []},
                {"type": "form", "fields": []},
                {"type": "cta", "text": "Comprar"},
            ],
        }],
    }
    project = _project(brief_json=brief)
    ctx = _ctx(fake_session, project)
    client = MagicMock()
    client.generate_image = AsyncMock()
    result = RedesignImagesAgent(openai_client=client).run(ctx)
    assert client.generate_image.call_count == 0
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_empty_slots"


# ---------- budget tracking ----------


def test_para_cuando_supera_budget(fake_session) -> None:
    """Budget pequeño + N slots → para al superar y crea ResidualTask."""
    brief = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [{
            "slug": "home", "title": "H", "intent": "landing",
            "sections": [
                {"type": "hero", "headline": "H1"},
                {"type": "image"},
                {"type": "gallery"},
                {"type": "testimonial"},
            ],
        }],
    }
    project = _project(brief_json=brief, budget=Decimal("0.10"))
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    # Cada llamada cuesta 0.04 → tras 3 llamadas (0.12) supera el budget.
    client.generate_image = AsyncMock(
        return_value=OpenAIImageResult(
            image_bytes=b"x", mime="image/png", width=1024, height=1024,
            cost_usd=0.041, model="gpt-image-2", quality="medium",
            size="1024x1024", prompt="p",
        )
    )
    result = RedesignImagesAgent(openai_client=client).run(ctx)

    assert result.outputs["budget_exhausted"] is True
    assert result.outputs["images_generated"] == 3
    # Residual emitido para el slot restante.
    assert result.outputs.get("skipped") is False


def test_resolve_budget_usa_default_si_none() -> None:
    project = MagicMock()
    project.image_generation_budget_usd = None
    assert RedesignImagesAgent._resolve_budget(project) == Decimal("1.00")


def test_resolve_budget_lee_del_project() -> None:
    project = MagicMock()
    project.image_generation_budget_usd = Decimal("3.50")
    assert RedesignImagesAgent._resolve_budget(project) == Decimal("3.50")


# ---------- error handling ----------


def test_openai_error_emite_residual_y_continua(fake_session) -> None:
    """Si una imagen falla, residual + warning, no para el pipeline."""
    brief = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [{
            "slug": "home", "title": "H", "intent": "landing",
            "sections": [
                {"type": "hero", "headline": "H1"},
                {"type": "image"},
            ],
        }],
    }
    project = _project(brief_json=brief)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_image = AsyncMock(
        side_effect=[
            OpenAIClientError("API error"),
            OpenAIImageResult(
                image_bytes=b"x", mime="image/png", width=1024, height=1024,
                cost_usd=0.053, model="gpt-image-2", quality="medium",
                size="1024x1024", prompt="p",
            ),
        ]
    )
    result = RedesignImagesAgent(openai_client=client).run(ctx)
    assert result.outputs["images_failed"] == 1
    assert result.outputs["images_generated"] == 1


# ---------- helpers estáticos ----------


def test_find_empty_image_slots_solo_image_types() -> None:
    brief = {
        "pages": [
            {
                "sections": [
                    {"type": "hero"},  # empty + image type → incluido
                    {"type": "hero", "asset_id": 5},  # tiene asset → excluido
                    {"type": "text"},  # tipo no imagen → excluido
                    {"type": "gallery"},  # empty + image → incluido
                    {"type": "image", "image_url": "https://x"},  # url ya → excluido
                ]
            }
        ]
    }
    slots = RedesignImagesAgent._find_empty_image_slots(brief)
    assert slots == [(0, 0, "hero"), (0, 3, "gallery")]


def test_image_section_types_incluye_hero_image_gallery() -> None:
    assert "hero" in _IMAGE_SECTION_TYPES
    assert "image" in _IMAGE_SECTION_TYPES
    assert "gallery" in _IMAGE_SECTION_TYPES
    assert "testimonial" in _IMAGE_SECTION_TYPES
    assert "text" not in _IMAGE_SECTION_TYPES


def test_build_prompt_incluye_business_brand_y_tone() -> None:
    prompt = RedesignImagesAgent._build_prompt(
        business={"name": "Acme", "description": "Joyería artesanal",
                  "sector": "portfolio", "tone_of_voice": "premium"},
        brand={"colors": {"primary": "#000", "secondary": "#fff"}},
        section={"type": "hero", "headline": "Bienvenido"},
        section_type="hero",
    )
    assert "Joyería artesanal" in prompt
    assert "portfolio" in prompt
    assert "premium" in prompt
    assert "#000" in prompt and "#fff" in prompt
