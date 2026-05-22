"""Tests del RedesignAIAgent (Sprint v0.25.0 B6).

Mockea OpenAIClient + sesión SQLAlchemy. NO hace llamadas reales.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.redesign_ai import RedesignAIAgent
from wcm_worker.errors import (
    OpenAIClientError,
    OpenAIInvalidOutputError,
    RedesignAgentError,
)
from wcm_worker.integrations.openai_client import OpenAIResult


def _project(
    *,
    id: int = 42,
    design_method: str | None = "ai",
    brief_json: dict | None = None,
    primary_lang: str = "es",
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.design_method = design_method
    p.brief_json = brief_json
    p.primary_lang = primary_lang
    return p


def _ctx(fake_session: MagicMock, project: MagicMock) -> AgentContext:
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None
    return AgentContext(session=fake_session, project_id=project.id)


# Brief mínimo válido (1 página, 1 sección).
_BRIEF = {
    "business": {"name": "Acme", "sector": "agency", "tone_of_voice": "formal"},
    "brand": {"colors": {"primary": "#000"}, "fonts": {}},
    "pages": [
        {
            "slug": "home",
            "title": "Home",
            "intent": "landing",
            "sections": [{"type": "hero", "headline": "Test"}],
        },
    ],
}

# JSON Bricks válido (esquema mínimo: section top-level).
_VALID_BRICKS = [
    {
        "id": "sec001",
        "name": "section",
        "parent": "0",
        "children": [],
        "settings": {},
    },
]

# JSON Bricks inválido (parent missing).
_INVALID_BRICKS = [
    {
        "id": "sec001",
        "name": "section",
        # parent ausente → schema falla
        "settings": {},
    },
]


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(RedesignAgentError, match="project_id"):
        RedesignAIAgent().run(AgentContext(session=fake_session))


def test_skipped_si_design_method_no_ai(fake_session) -> None:
    project = _project(design_method="templates")
    ctx = _ctx(fake_session, project)
    result = RedesignAIAgent(openai_client=MagicMock()).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "design_method_mismatch"


def test_skipped_si_sin_brief(fake_session) -> None:
    project = _project(brief_json=None)
    ctx = _ctx(fake_session, project)
    result = RedesignAIAgent(openai_client=MagicMock()).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_brief"


def test_skipped_si_sin_openai_key(fake_session, monkeypatch) -> None:
    """Sin API key (from_env devuelve None) → SKIPPED."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)
    # openai_client=None y no env var
    result = RedesignAIAgent(openai_client=None).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_openai_key"


# ---------- happy path ----------


def test_genera_pagina_valid_bricks(fake_session) -> None:
    """Caso happy: OpenAI devuelve content válido → bricks_page upserted."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    fake_result = OpenAIResult(
        data={"content": _VALID_BRICKS},
        tokens_in=1500, tokens_out=800, cost_usd=0.012, model="gpt-4o",
    )
    client = MagicMock()
    client.generate_page_redesign = AsyncMock(return_value=fake_result)

    added = []
    fake_session.add.side_effect = lambda x: added.append(x)

    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert result.outputs["pages_generated"] == 1
    assert result.outputs["pages_failed"] == 0
    assert result.outputs["cost_usd_total"] == 0.012
    assert client.generate_page_redesign.call_count == 1

    bricks_pages = [x for x in added if type(x).__name__ == "BricksPage"]
    assert len(bricks_pages) == 1
    assert bricks_pages[0].slug == "home"


def test_retry_si_validacion_falla(fake_session) -> None:
    """Validación falla → 1 retry con error context. Si retry pasa, OK."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    invalid_result = OpenAIResult(
        data={"content": _INVALID_BRICKS},
        tokens_in=1000, tokens_out=500, cost_usd=0.008, model="gpt-4o",
    )
    valid_result = OpenAIResult(
        data={"content": _VALID_BRICKS},
        tokens_in=1200, tokens_out=600, cost_usd=0.010, model="gpt-4o",
    )
    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        side_effect=[invalid_result, valid_result]
    )

    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert result.outputs["pages_generated"] == 1
    assert client.generate_page_redesign.call_count == 2
    # Coste sumado de ambos calls (tolerancia float).
    assert abs(result.outputs["cost_usd_total"] - 0.018) < 1e-9


def test_fallback_templates_si_retry_falla(fake_session) -> None:
    """Si retry también falla y hay fallback agent → invoca templates."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    invalid_result = OpenAIResult(
        data={"content": _INVALID_BRICKS},
        tokens_in=1000, tokens_out=500, cost_usd=0.008, model="gpt-4o",
    )
    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        side_effect=[invalid_result, invalid_result]
    )

    fallback = MagicMock()
    fallback_result = MagicMock()
    fallback_result.outputs = {"pages_generated": 1}
    fallback.run.return_value = fallback_result

    result = RedesignAIAgent(
        openai_client=client, fallback_agent=fallback,
    ).run(ctx)

    assert result.outputs["pages_generated"] == 0  # AI no generó
    assert result.outputs["pages_fallback"] == 1
    fallback.run.assert_called_once()


def test_openai_error_fallback_templates(fake_session) -> None:
    """OpenAI lanza error → fallback se intenta."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        side_effect=OpenAIClientError("API down")
    )

    fallback = MagicMock()
    fallback_result = MagicMock()
    fallback_result.outputs = {"pages_generated": 1}
    fallback.run.return_value = fallback_result

    result = RedesignAIAgent(
        openai_client=client, fallback_agent=fallback,
    ).run(ctx)

    assert result.outputs["pages_fallback"] == 1
    assert result.outputs["pages_failed"] == 0


def test_openai_error_sin_fallback_marca_failed(fake_session) -> None:
    """OpenAI falla y NO hay fallback configurado → pages_failed += 1."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        side_effect=OpenAIClientError("rate limit")
    )

    result = RedesignAIAgent(openai_client=client).run(ctx)  # sin fallback

    assert result.outputs["pages_failed"] == 1
    assert result.outputs["pages_generated"] == 0
    assert any("rate limit" in w for w in result.warnings)


def test_invalid_output_sin_fallback_marca_failed(fake_session) -> None:
    """OpenAIInvalidOutputError sin fallback → pages_failed."""
    project = _project(brief_json=_BRIEF)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        side_effect=OpenAIInvalidOutputError("malformed JSON")
    )

    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert result.outputs["pages_failed"] == 1
    assert any("inválido" in w for w in result.warnings)


def test_multiple_pages_se_procesan_secuencialmente(fake_session) -> None:
    """Brief con 3 páginas → 3 calls OpenAI secuenciales."""
    brief_3pages = {
        **_BRIEF,
        "pages": [
            {"slug": "home", "title": "Home", "sections": [{"type": "hero"}]},
            {"slug": "about", "title": "About", "sections": [{"type": "hero"}]},
            {"slug": "contact", "title": "Contact", "sections": [{"type": "cta"}]},
        ],
    }
    project = _project(brief_json=brief_3pages)
    ctx = _ctx(fake_session, project)

    client = MagicMock()
    client.generate_page_redesign = AsyncMock(
        return_value=OpenAIResult(
            data={"content": _VALID_BRICKS},
            tokens_in=1000, tokens_out=500, cost_usd=0.009, model="gpt-4o",
        )
    )

    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert result.outputs["pages_generated"] == 3
    assert client.generate_page_redesign.call_count == 3
    assert abs(result.outputs["cost_usd_total"] - 0.027) < 1e-9


# ---------- v0.26.0 — Hybrid mode (sección a sección) ----------


def _hybrid_brief() -> dict:
    """Brief con 2 secciones: una AI, otra templates."""
    return {
        "business": {"name": "Acme", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {"primary": "#000"}, "fonts": {}},
        "pages": [
            {
                "slug": "home",
                "title": "Home",
                "intent": "landing",
                "sections": [
                    {"type": "hero", "design_method": "ai", "headline": "Test"},
                    {"type": "text", "design_method": "templates", "html": "<p>x</p>"},
                ],
            },
        ],
    }


def _existing_bricks_page_with_placeholders():
    """Mock de un BricksPage existente con placeholder _pending_ai
    para sección 0 + chunk de templates para sección 1."""
    bp = MagicMock()
    bp.bricks_json = [
        {
            "id": "pai000",
            "name": "section",
            "parent": "0",
            "children": [],
            "settings": {
                "_brief_section_index": 0,
                "_pending_ai": True,
                "_brief_section_type": "hero",
            },
        },
        {
            "id": "tpl001",
            "name": "section",
            "parent": "0",
            "children": ["txt001"],
            "settings": {"_brief_section_index": 1},
        },
        {
            "id": "txt001",
            "name": "text-basic",
            "parent": "tpl001",
            "settings": {"text": "Texto template"},
        },
    ]
    return bp


def _hybrid_ctx(fake_session, project, existing_bp):
    """Setup ctx para hybrid: session.execute devuelve el bricks_page existente."""
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = existing_bp
    return AgentContext(session=fake_session, project_id=project.id)


def test_hybrid_skipped_si_design_method_templates(fake_session) -> None:
    project = _project(design_method="templates", brief_json=_hybrid_brief())
    ctx = _ctx(fake_session, project)
    client = MagicMock()
    result = RedesignAIAgent(openai_client=client).run(ctx)
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "design_method_mismatch"


def test_hybrid_genera_solo_secciones_ai(fake_session) -> None:
    """En modo Hybrid (design_method=None), AI solo procesa secciones
    con design_method=ai y mergea con el bricks_pages existente."""
    project = _project(design_method=None, brief_json=_hybrid_brief())
    existing_bp = _existing_bricks_page_with_placeholders()
    ctx = _hybrid_ctx(fake_session, project, existing_bp)

    new_subtree = [
        {
            "id": "ai0001",
            "name": "section",
            "parent": "0",
            "children": ["ai0002"],
            "settings": {"_padding": {"top": "80px"}},
        },
        {
            "id": "ai0002",
            "name": "heading",
            "parent": "ai0001",
            "settings": {"text": "Hola AI"},
        },
    ]
    client = MagicMock()
    client.generate_section_redesign = AsyncMock(
        return_value=OpenAIResult(
            data={"content": new_subtree},
            tokens_in=500, tokens_out=200, cost_usd=0.012, model="gpt-5.5",
        )
    )

    result = RedesignAIAgent(openai_client=client).run(ctx)

    # Solo se llama una vez (1 sección AI).
    assert client.generate_section_redesign.call_count == 1
    assert result.outputs["mode"] == "hybrid"
    assert result.outputs["sections_generated"] == 1
    assert result.outputs["sections_failed"] == 0
    # El placeholder fue reemplazado en bricks_json y el chunk template
    # de la sección 1 permanece intacto.
    final = existing_bp.bricks_json
    ids = [el["id"] for el in final]
    assert "pai000" not in ids  # placeholder eliminado
    assert "ai0001" in ids and "ai0002" in ids  # AI subtree insertado
    assert "tpl001" in ids and "txt001" in ids  # template intacto
    # El root AI tiene el marker correcto y sin _pending_ai.
    ai_root = next(el for el in final if el["id"] == "ai0001")
    assert ai_root["settings"]["_brief_section_index"] == 0
    assert "_pending_ai" not in ai_root["settings"]


def test_hybrid_sin_bricks_pages_existente_emite_warning(fake_session) -> None:
    """Si Templates no corrió antes en Hybrid, AI emite warning y skip
    esa página."""
    project = _project(design_method=None, brief_json=_hybrid_brief())
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None
    ctx = AgentContext(session=fake_session, project_id=project.id)

    client = MagicMock()
    client.generate_section_redesign = AsyncMock()  # nunca se llama
    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert client.generate_section_redesign.call_count == 0
    assert result.outputs["sections_generated"] == 0
    assert any("bricks_pages previo" in w for w in result.warnings)


def test_hybrid_sin_secciones_ai_no_llama_openai(fake_session) -> None:
    """Página con todas las secciones design_method=templates → 0 calls."""
    brief_all_templates = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [
            {
                "slug": "home", "title": "H", "intent": "landing",
                "sections": [
                    {"type": "text", "design_method": "templates", "html": "<p>x</p>"},
                ],
            },
        ],
    }
    project = _project(design_method=None, brief_json=brief_all_templates)
    fake_session.get.return_value = project
    # No se llega a consultar BricksPage porque ai_indices=[] return early.
    ctx = AgentContext(session=fake_session, project_id=project.id)

    client = MagicMock()
    client.generate_section_redesign = AsyncMock()
    result = RedesignAIAgent(openai_client=client).run(ctx)

    assert client.generate_section_redesign.call_count == 0
    assert result.outputs["sections_generated"] == 0


def test_merge_subtree_by_index_preserva_orden() -> None:
    """Helper estático: insertar subtree en la posición original del root."""
    current = [
        {"id": "sec000", "name": "section", "parent": "0", "settings": {"_brief_section_index": 0}},
        {"id": "child0", "name": "text-basic", "parent": "sec000", "settings": {}},
        {"id": "pai001", "name": "section", "parent": "0", "settings": {"_brief_section_index": 1, "_pending_ai": True}},
        {"id": "sec002", "name": "section", "parent": "0", "settings": {"_brief_section_index": 2}},
    ]
    new_subtree = [
        {"id": "new001", "name": "section", "parent": "0", "settings": {}},
        {"id": "new002", "name": "heading", "parent": "new001", "settings": {}},
    ]
    merged = RedesignAIAgent._merge_subtree_by_index(
        current, section_index=1, new_subtree=new_subtree,
    )
    ids = [el["id"] for el in merged]
    # El nuevo subtree ocupa la posición del placeholder (entre child0 y sec002).
    assert ids == ["sec000", "child0", "new001", "new002", "sec002"]


def test_merge_subtree_by_index_no_encuentra_root_apend() -> None:
    """Si no hay root con ese index, apéndalo al final."""
    current = [
        {"id": "sec000", "name": "section", "parent": "0", "settings": {"_brief_section_index": 0}},
    ]
    new_subtree = [
        {"id": "new001", "name": "section", "parent": "0", "settings": {}},
    ]
    merged = RedesignAIAgent._merge_subtree_by_index(
        current, section_index=42, new_subtree=new_subtree,
    )
    assert [el["id"] for el in merged] == ["sec000", "new001"]
