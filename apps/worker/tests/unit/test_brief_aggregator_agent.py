"""Tests del BriefSectionAggregator (Sprint v0.29.0 B3-B5).

Mockea OpenAIClient.aggregate_page_sections + sesión SQLAlchemy.
Verifica cache, validación, fast-path, idempotencia.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.brief_aggregator import BriefSectionAggregator
from wcm_worker.errors import (
    BriefAggregatorError,
    OpenAIClientError,
    OpenAIInvalidOutputError,
)
from wcm_worker.integrations.openai_client import OpenAIResult

# ---------- helpers ----------


def _project(
    *,
    id: int = 42,
    brief_json: dict | None = None,
    cache: dict | None = None,
    cost_usd: Decimal | None = None,
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.brief_json = brief_json
    p.brief_aggregation_cache_json = cache
    p.brief_aggregation_cost_usd = cost_usd if cost_usd is not None else Decimal("0.0")
    p.business_sector = "agency"
    return p


def _ctx(project: MagicMock) -> AgentContext:
    session = MagicMock()
    session.get.return_value = project
    return AgentContext(session=session, project_id=project.id)


def _brief_with_low_level_sections() -> dict:
    """Brief típico v0.28.0: 5 bloques planos en home (caso WCM-053)."""
    return {
        "business": {"name": "Acme", "sector": "agency"},
        "brand": {},
        "pages": [
            {
                "slug": "home",
                "title": "Home",
                "intent": "landing",
                "sections": [
                    {"type": "heading", "text": "Bienvenido", "design_method": "templates"},
                    {"type": "text", "html": "<p>Somos creativos</p>", "design_method": "templates"},
                    {"type": "image", "asset_id": 7, "alt": "team", "design_method": "templates"},
                    {"type": "heading", "text": "Servicios", "design_method": "templates"},
                    {"type": "grid", "items": [{}, {}, {}], "design_method": "templates"},
                ],
            }
        ],
    }


def _llm_response_grouping_5_blocks_to_2_sections() -> OpenAIResult:
    return OpenAIResult(
        data={
            "sections": [
                {
                    "type": "hero",
                    "source_block_ids": [0, 1, 2],
                    "headline": "Bienvenido",
                    "has_image": True,
                    "has_cta": False,
                },
                {
                    "type": "features",
                    "source_block_ids": [3, 4],
                    "headline": "Servicios",
                    "has_image": False,
                    "has_cta": False,
                },
            ]
        },
        tokens_in=800, tokens_out=300,
        cost_usd=0.012, model="gpt-5.5",
    )


# ---------- run() — preconditions ----------


def test_run_sin_project_id_lanza_error() -> None:
    agent = BriefSectionAggregator()
    ctx = AgentContext(session=MagicMock(), project_id=None)
    with pytest.raises(BriefAggregatorError, match="requiere project_id"):
        agent.run(ctx)


def test_run_sin_project_en_db_lanza_error() -> None:
    session = MagicMock()
    session.get.return_value = None
    ctx = AgentContext(session=session, project_id=999)
    agent = BriefSectionAggregator()
    with pytest.raises(BriefAggregatorError, match="no existe"):
        agent.run(ctx)


def test_run_sin_brief_json_skipped() -> None:
    project = _project(brief_json=None)
    agent = BriefSectionAggregator(openai_client=MagicMock())
    result = agent.run(_ctx(project))
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_brief"


def test_run_brief_sin_pages_skipped() -> None:
    project = _project(brief_json={"business": {}, "pages": []})
    agent = BriefSectionAggregator(openai_client=MagicMock())
    result = agent.run(_ctx(project))
    assert result.outputs["skipped"] is True


def test_run_sin_openai_client_skipped_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project = _project(brief_json=_brief_with_low_level_sections())
    agent = BriefSectionAggregator()  # sin client inyectado
    result = agent.run(_ctx(project))
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_openai_key"
    assert any("OPENAI_API_KEY" in w for w in result.warnings)


# ---------- happy path ----------


def test_run_happy_path_agrupa_y_persiste() -> None:
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=_llm_response_grouping_5_blocks_to_2_sections()
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))

    assert result.outputs["skipped"] is False
    assert result.outputs["n_pages_aggregated_llm"] == 1
    assert result.outputs["n_pages_cache_hit"] == 0
    assert result.outputs["n_sections_before"] == 5
    assert result.outputs["n_sections_after"] == 2
    assert result.outputs["cost_session_usd"] == pytest.approx(0.012)

    # Brief mutado: 2 secciones canónicas con source_blocks
    home = project.brief_json["pages"][0]
    assert len(home["sections"]) == 2
    assert home["sections"][0]["type"] == "hero"
    assert home["sections"][1]["type"] == "features"
    assert home["sections"][0]["has_image"] is True
    assert len(home["sections"][0]["source_blocks"]) == 3
    assert home["aggregated_at"]
    assert home["aggregation_method"] == "llm"

    # Cache populated
    assert project.brief_aggregation_cache_json
    assert len(project.brief_aggregation_cache_json) == 1
    # Cost accumulated
    assert project.brief_aggregation_cost_usd == Decimal("0.012")


def test_run_cache_hit_no_llamada_a_openai() -> None:
    """Segunda corrida con mismo blocks_sha reusa cache (sin coste extra)."""
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=_llm_response_grouping_5_blocks_to_2_sections()
    )
    agent = BriefSectionAggregator(openai_client=client)

    # 1er run
    agent.run(_ctx(project))
    assert client.aggregate_page_sections.call_count == 1
    cost_after_first = project.brief_aggregation_cost_usd

    # 2nd run con MISMOS blocks (reset brief sections a estado pre-aggregated
    # para simular re-ejecución del pipeline tras un fallo posterior)
    project.brief_json = _brief_with_low_level_sections()

    result2 = agent.run(_ctx(project))
    # No nueva llamada
    assert client.aggregate_page_sections.call_count == 1
    assert result2.outputs["n_pages_cache_hit"] == 1
    assert result2.outputs["n_pages_aggregated_llm"] == 0
    assert result2.outputs["cost_session_usd"] == 0.0
    # Coste acumulado no cambia
    assert project.brief_aggregation_cost_usd == cost_after_first
    # Brief ahora tiene aggregation_method=cache
    assert project.brief_json["pages"][0]["aggregation_method"] == "cache"


# ---------- validación de output LLM ----------


def test_run_emite_warning_si_type_fuera_de_taxonomia() -> None:
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=OpenAIResult(
            data={"sections": [
                {"type": "neverexistedtype", "source_block_ids": [0, 1, 2, 3, 4]}
            ]},
            tokens_in=10, tokens_out=10, cost_usd=0.001, model="gpt-5.5",
        )
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1
    assert result.outputs["n_pages_aggregated_llm"] == 0
    assert any("inválido" in w for w in result.warnings)
    # El Brief queda intacto (no se mutaron las sections)
    assert project.brief_json["pages"][0]["sections"][0]["type"] == "heading"


def test_run_emite_warning_si_source_block_ids_no_cubren_todos() -> None:
    """LLM debe cubrir TODOS los bloques. Si deja huecos, fallo."""
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=OpenAIResult(
            data={"sections": [
                {"type": "hero", "source_block_ids": [0, 1, 2]},
                # bloques 3 y 4 sin cubrir
            ]},
            tokens_in=10, tokens_out=10, cost_usd=0.001, model="gpt-5.5",
        )
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1
    assert any("inválido" in w for w in result.warnings)


def test_run_emite_warning_si_source_block_ids_solapan() -> None:
    """Bloques no pueden estar en 2 secciones distintas."""
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=OpenAIResult(
            data={"sections": [
                {"type": "hero", "source_block_ids": [0, 1, 2]},
                {"type": "features", "source_block_ids": [2, 3, 4]},  # 2 duplicado
            ]},
            tokens_in=10, tokens_out=10, cost_usd=0.001, model="gpt-5.5",
        )
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1


def test_run_emite_warning_si_source_block_ids_fuera_de_rango() -> None:
    """IDs >= n_blocks o negativos rompen validación."""
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        return_value=OpenAIResult(
            data={"sections": [
                {"type": "hero", "source_block_ids": [0, 1, 2, 3, 99]},  # 99 fuera
            ]},
            tokens_in=10, tokens_out=10, cost_usd=0.001, model="gpt-5.5",
        )
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1


# ---------- error handling ----------


def test_run_openai_falla_marca_skipped_con_warning() -> None:
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        side_effect=OpenAIClientError("API down")
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1
    assert any("OpenAIClientError" in w for w in result.warnings)


def test_run_openai_invalid_output_marca_skipped() -> None:
    project = _project(brief_json=_brief_with_low_level_sections())
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock(
        side_effect=OpenAIInvalidOutputError("schema mismatch")
    )
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1


# ---------- fast-path para páginas triviales ----------


def test_fastpath_un_solo_bloque_hero_no_llama_llm() -> None:
    """Página con 1 solo bloque tipo `hero` se mapea directo sin LLM."""
    project = _project(brief_json={
        "business": {"name": "X", "sector": "agency"},
        "brand": {},
        "pages": [
            {
                "slug": "home",
                "intent": "landing",
                "sections": [
                    {"type": "hero", "headline": "Hi", "design_method": "ai"},
                ],
            }
        ],
    })
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock()
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_fastpath"] == 1
    assert result.outputs["n_pages_aggregated_llm"] == 0
    client.aggregate_page_sections.assert_not_called()
    home = project.brief_json["pages"][0]
    assert home["sections"][0]["type"] == "hero"
    assert home["aggregation_method"] == "fastpath"


def test_fastpath_un_solo_bloque_ambiguo_skipped() -> None:
    """Bloque `text` standalone no tiene mapping directo → skipped sin LLM."""
    project = _project(brief_json={
        "business": {"sector": "agency"},
        "brand": {},
        "pages": [
            {
                "slug": "404",
                "sections": [{"type": "text", "html": "<p>oops</p>"}],
            }
        ],
    })
    client = MagicMock()
    client.aggregate_page_sections = AsyncMock()
    agent = BriefSectionAggregator(openai_client=client)
    result = agent.run(_ctx(project))
    assert result.outputs["n_pages_skipped"] == 1
    client.aggregate_page_sections.assert_not_called()


# ---------- helpers internos ----------


def test_compute_blocks_sha_estable_e_independiente_del_orden_de_keys() -> None:
    blocks_a = [
        {"type": "heading", "text": "Hola", "design_method": "x"},
        {"type": "text", "html": "<p>Y</p>"},
    ]
    blocks_b = [
        {"design_method": "x", "text": "Hola", "type": "heading"},  # mismo, otro orden
        {"html": "<p>Y</p>", "type": "text"},
    ]
    sha_a = BriefSectionAggregator._compute_blocks_sha(blocks_a, "home")
    sha_b = BriefSectionAggregator._compute_blocks_sha(blocks_b, "home")
    assert sha_a == sha_b
    # Cambiar intent cambia el sha
    sha_c = BriefSectionAggregator._compute_blocks_sha(blocks_a, "contact")
    assert sha_a != sha_c


def test_compute_blocks_sha_distinto_si_text_distinto() -> None:
    a = [{"type": "text", "html": "<p>uno</p>"}]
    b = [{"type": "text", "html": "<p>dos</p>"}]
    assert BriefSectionAggregator._compute_blocks_sha(a, None) != \
           BriefSectionAggregator._compute_blocks_sha(b, None)


def test_validate_and_build_sections_returns_none_si_lista_vacia() -> None:
    out = BriefSectionAggregator._validate_and_build_sections(
        [], source_blocks=[{"type": "x"}], page_slug="s",
    )
    assert out is None


def test_validate_and_build_sections_hereda_design_method_del_primer_bloque() -> None:
    out = BriefSectionAggregator._validate_and_build_sections(
        [{"type": "hero", "source_block_ids": [0, 1]}],
        source_blocks=[
            {"type": "heading", "design_method": "ai"},
            {"type": "image"},
        ],
        page_slug="home",
    )
    assert out is not None
    assert out[0]["design_method"] == "ai"
