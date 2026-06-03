"""Tests del OpenAIClient (Sprint v0.25.0 Bloque B1).

Mockea `openai.AsyncOpenAI` para no hacer llamadas reales.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.errors import (
    OpenAIAuthError,
    OpenAIInvalidOutputError,
    OpenAIRateLimitError,
)
from wcm_worker.integrations.openai_client import (
    DEFAULT_MODEL_METADATA,
    DEFAULT_MODEL_REDESIGN,
    OpenAIClient,
    OpenAIResult,
    _estimate_cost,
)


def _mock_response(tool_name: str, args: dict, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    """Helper que construye una response OpenAI ChatCompletion fake."""
    r = MagicMock()
    tc = MagicMock()
    tc.function = MagicMock()
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(args)
    r.choices = [MagicMock()]
    r.choices[0].message = MagicMock()
    r.choices[0].message.tool_calls = [tc]
    r.usage = MagicMock()
    r.usage.prompt_tokens = prompt_tokens
    r.usage.completion_tokens = completion_tokens
    return r


# ---------- helpers ----------


def test_estimate_cost_gpt4o_mini() -> None:
    """gpt-4o-mini: $0.15/MTok in, $0.60/MTok out. 1k+1k tokens = $0.00075."""
    cost = _estimate_cost("gpt-4o-mini", 1000, 1000)
    assert abs(cost - 0.00075) < 1e-9


def test_estimate_cost_gpt4o() -> None:
    """gpt-4o: $2.50/MTok in, $10/MTok out. 1k+1k tokens = $0.0125."""
    cost = _estimate_cost("gpt-4o", 1000, 1000)
    assert abs(cost - 0.0125) < 1e-9


def test_estimate_cost_unknown_model() -> None:
    assert _estimate_cost("custom-fine-tune", 1000, 1000) == 0.0


# ---------- preconditions ----------


def test_client_requires_api_key() -> None:
    with pytest.raises(OpenAIAuthError, match="OPENAI_API_KEY"):
        OpenAIClient(api_key="")


def test_from_env_returns_none_sin_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIClient.from_env() is None


def test_from_env_construye_con_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key-1234")
    monkeypatch.setenv("OPENAI_MODEL_METADATA", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_MODEL_REDESIGN", "gpt-4o")
    client = OpenAIClient.from_env()
    assert client is not None
    assert client.api_key == "sk-fake-test-key-1234"
    assert client.model_metadata == "gpt-4o-mini"
    assert client.model_redesign == "gpt-4o"


# ---------- generate_brief_metadata ----------


@pytest.mark.asyncio
async def test_generate_brief_metadata_happy_path() -> None:
    """Devuelve dict con los 5 campos. Cost USD calculado."""
    fake_args = {
        "business_description": "Estudio de diseño de joyas artesanales en Madrid.",
        "business_sector": "portfolio",
        "tone_of_voice": "premium",
        "target_audience": "mujeres 35-55 con poder adquisitivo alto.",
        "usps": ["Joyería artesanal", "Piezas únicas", "Diseños exclusivos"],
    }
    client = OpenAIClient(api_key="sk-fake")
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(
        return_value=_mock_response(
            "emit_brief_metadata", fake_args, prompt_tokens=500, completion_tokens=200
        )
    )
    result = await client.generate_brief_metadata(
        scraping_summary="Estudio de joyas artesanales. Diseños únicos.",
    )
    assert isinstance(result, OpenAIResult)
    assert result.data["business_sector"] == "portfolio"
    assert result.data["tone_of_voice"] == "premium"
    assert len(result.data["usps"]) == 3
    assert result.tokens_in == 500
    assert result.tokens_out == 200
    assert result.cost_usd > 0
    assert result.model == DEFAULT_MODEL_METADATA


@pytest.mark.asyncio
async def test_generate_page_redesign_happy_path() -> None:
    """Genera array `content` Bricks válido."""
    fake_args = {
        "content": [
            {
                "id": "sec001",
                "name": "section",
                "parent": "0",
                "children": ["hed001"],
                "settings": {"_padding": {"top": "80px", "right": "24px", "bottom": "80px", "left": "24px"}},
            },
            {
                "id": "hed001",
                "name": "heading",
                "parent": "sec001",
                "children": [],
                "settings": {"text": "Joyería única", "tag": "h1"},
            },
        ],
        "notes": "Hero limpio centrado.",
    }
    client = OpenAIClient(api_key="sk-fake")
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(
        return_value=_mock_response(
            "emit_bricks_page", fake_args, prompt_tokens=1500, completion_tokens=800
        )
    )
    result = await client.generate_page_redesign(
        brief={"business": {"name": "Joyas Lola"}, "brand": {"colors": {}}},
        page_spec={"slug": "home", "sections": [{"type": "hero"}]},
    )
    assert len(result.data["content"]) == 2
    assert result.data["content"][0]["name"] == "section"
    assert result.model == DEFAULT_MODEL_REDESIGN


# ---------- error handling ----------


@pytest.mark.asyncio
async def test_auth_error_no_retriable() -> None:
    """401 lanza OpenAIAuthError inmediatamente, sin retry."""
    client = OpenAIClient(api_key="sk-fake")
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(
        side_effect=Exception("401 Unauthorized: invalid API key")
    )
    with pytest.raises(OpenAIAuthError):
        await client.generate_brief_metadata(scraping_summary="x")
    # Solo 1 call (sin retry).
    assert client._client.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_rate_limit_error_se_clasifica_correctamente() -> None:
    """429 levanta OpenAIRateLimitError (sigue subiendo el último intento)."""
    client = OpenAIClient(api_key="sk-fake", retries=1)
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(
        side_effect=Exception("429 Too Many Requests")
    )
    with pytest.raises(OpenAIRateLimitError):
        await client.generate_brief_metadata(scraping_summary="x")


@pytest.mark.asyncio
async def test_invalid_output_si_tool_no_invocada() -> None:
    """Si el modelo NO invoca la tool, OpenAIInvalidOutputError."""
    client = OpenAIClient(api_key="sk-fake")
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message = MagicMock()
    fake_resp.choices[0].message.tool_calls = []  # vacío
    fake_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10)
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=fake_resp)
    with pytest.raises(OpenAIInvalidOutputError, match="no invocó la tool"):
        await client.generate_brief_metadata(scraping_summary="x")


@pytest.mark.asyncio
async def test_invalid_output_si_json_corrupto() -> None:
    """Si arguments no parsea JSON, OpenAIInvalidOutputError."""
    client = OpenAIClient(api_key="sk-fake")
    fake_resp = MagicMock()
    tc = MagicMock()
    tc.function = MagicMock()
    tc.function.name = "emit_brief_metadata"
    tc.function.arguments = "{invalid json}"
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message = MagicMock()
    fake_resp.choices[0].message.tool_calls = [tc]
    fake_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10)
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=fake_resp)
    with pytest.raises(OpenAIInvalidOutputError, match="JSON válido"):
        await client.generate_brief_metadata(scraping_summary="x")


# ---------- user message construction ----------


def test_brief_metadata_user_msg_trunca_scraping_largo() -> None:
    """Scraping >8KB se trunca con marker."""
    long_text = "x" * (10 * 1024)  # 10KB
    msg = OpenAIClient._build_brief_metadata_user_message(
        scraping_summary=long_text, theme_hints={}, fingerprint={},
    )
    assert "<!-- TRUNCATED -->" in msg


def test_brief_metadata_user_msg_incluye_theme_y_fingerprint() -> None:
    msg = OpenAIClient._build_brief_metadata_user_message(
        scraping_summary="Web de joyería",
        theme_hints={"colors": {"primary": "#b1f100"}},
        fingerprint={"sector_pre_inferred": "luxury"},
    )
    assert "joyería" in msg.lower()
    assert "b1f100" in msg
    assert "luxury" in msg


def test_page_redesign_user_msg_incluye_brief_y_page_spec() -> None:
    msg = OpenAIClient._build_page_redesign_user_message(
        brief={"business": {"name": "Mariya"}, "brand": {"colors": {"primary": "#000"}}},
        page_spec={"slug": "home", "intent": "landing"},
    )
    assert "Mariya" in msg
    assert "home" in msg
    assert "var(--bricks-color-" in msg  # instructiva


# ---------- aggregate_page_sections (v0.29.0 B2) ----------


@pytest.mark.asyncio
async def test_aggregate_page_sections_happy_path() -> None:
    """Devuelve {sections: [...]} con tipos canónicos + source_block_ids."""
    fake_args = {
        "sections": [
            {
                "type": "hero",
                "source_block_ids": [0, 1, 2],
                "headline": "Joyas únicas",
                "subheadline": "Diseños artesanales en Madrid",
                "summary": "Hero con imagen de modelo + CTA reservar cita",
                "has_image": True,
                "has_cta": True,
            },
            {
                "type": "features",
                "source_block_ids": [3, 4, 5, 6],
                "summary": "3 servicios destacados con icono",
                "has_image": False,
                "has_cta": False,
            },
            {
                "type": "footer",
                "source_block_ids": [7],
                "has_image": False,
                "has_cta": False,
            },
        ]
    }
    client = OpenAIClient(api_key="sk-fake")
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(
        return_value=_mock_response(
            "emit_semantic_sections", fake_args,
            prompt_tokens=1200, completion_tokens=350,
        )
    )
    result = await client.aggregate_page_sections(
        page_url="https://mariya.design/about",
        page_intent="about",
        blocks=[
            {"block_type": "heading", "content_json": {"text": "Sobre"}},
            {"block_type": "image", "content_json": {"alt": "team"}},
            {"block_type": "cta", "content_json": {"cta_text": "Reservar"}},
            {"block_type": "heading", "content_json": {"text": "Nuestros servicios"}},
            {"block_type": "grid", "content_json": {"items": [1, 2, 3]}},
            {"block_type": "text", "content_json": {"html": "<p>Servicio 1</p>"}},
            {"block_type": "text", "content_json": {"html": "<p>Servicio 2</p>"}},
            {"block_type": "text", "content_json": {"html": "<p>Footer info</p>"}},
        ],
        business_sector="luxury",
        canonical_taxonomy={"hero": "first", "features": "3+ items", "footer": "last"},
    )
    assert isinstance(result, OpenAIResult)
    assert len(result.data["sections"]) == 3
    assert result.data["sections"][0]["type"] == "hero"
    assert result.data["sections"][2]["type"] == "footer"
    # source_block_ids cubren todos los bloques 0..7 sin huecos
    all_ids = [
        bid for s in result.data["sections"] for bid in s["source_block_ids"]
    ]
    assert sorted(all_ids) == list(range(8))
    assert result.tokens_in == 1200
    assert result.cost_usd > 0


@pytest.mark.asyncio
async def test_aggregate_page_sections_invalid_output_si_tool_no_invocada() -> None:
    client = OpenAIClient(api_key="sk-fake")
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message = MagicMock()
    fake_resp.choices[0].message.tool_calls = []
    fake_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10)
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=fake_resp)
    with pytest.raises(OpenAIInvalidOutputError):
        await client.aggregate_page_sections(
            page_url="x", page_intent=None, blocks=[], business_sector=None,
        )


def test_aggregate_user_msg_compacta_bloques_con_snippet_limpio() -> None:
    """El user message convierte HTML a texto plano + cap a 120 chars."""
    long_html = "<p>" + ("Texto muy largo. " * 30) + "</p>"
    msg = OpenAIClient._build_aggregate_sections_user_message(
        page_url="https://example.com/",
        page_intent="home",
        blocks=[
            {"block_type": "text", "content_json": {"html": long_html}},
            {"block_type": "image", "content_json": {"alt": "logo big"}},
            {"block_type": "cta", "content_json": {"cta_text": "Comprar"}},
            {"block_type": "grid", "content_json": {"items": [1, 2, 3, 4]}},
        ],
        business_sector="ecommerce",
        canonical_taxonomy={"hero": "first", "cta": "..."},
    )
    # No queda HTML en el snippet
    assert "<p>" not in msg
    assert "</p>" not in msg
    # Cada snippet capado a 120 chars (verificable indirectamente)
    assert "Texto muy largo" in msg
    # Items grid se etiqueta como "[N items]"
    assert "[4 items]" in msg
    assert "[CTA] Comprar" in msg
    assert "[image] logo big" in msg


def test_aggregate_user_msg_incluye_taxonomy_completa() -> None:
    msg = OpenAIClient._build_aggregate_sections_user_message(
        page_url="x", page_intent="home", blocks=[],
        business_sector=None,
        canonical_taxonomy={
            "hero": "first impact",
            "features": "list of services",
            "cta": "call to action",
        },
    )
    assert "first impact" in msg
    assert "list of services" in msg
    assert "Taxonomía canónica" in msg


def test_aggregate_user_msg_sector_opcional() -> None:
    """Si business_sector es None, sigue funcionando."""
    msg = OpenAIClient._build_aggregate_sections_user_message(
        page_url="https://x.com",
        page_intent=None,
        blocks=[{"block_type": "heading", "content_json": {"text": "Hi"}}],
        business_sector=None,
        canonical_taxonomy={"hero": "x"},
    )
    assert "(no especificado)" in msg
