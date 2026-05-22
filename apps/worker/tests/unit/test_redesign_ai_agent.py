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
