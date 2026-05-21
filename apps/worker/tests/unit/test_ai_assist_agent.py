"""Tests del AiAssistAgent (AI.4 — sprint v0.22.0).

Mockea ClaudeVisionClient y httpx.AsyncClient. NO hace llamadas reales.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from wcm_types.enums import BlockType
from wcm_worker.agents.ai_assist import (
    DEFAULT_BUDGET_USD,
    DEFAULT_COVERAGE_THRESHOLD,
    AiAssistAgent,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.errors import AiAssistError
from wcm_worker.integrations.claude_vision import (
    ClaudeVisionApiError,
    ClaudeVisionAuthError,
    ClaudeVisionResult,
)


def _block(
    *,
    id: int = 1,
    block_type: BlockType = BlockType.UNKNOWN,
    coverage_score: float | None = None,
    screenshot_url: str | None = "https://r2/section.png",
    ai_processed: bool = False,
    content_json: dict | None = None,
    page_id: int = 100,
) -> MagicMock:
    b = MagicMock()
    b.id = id
    b.project_id = 42
    b.page_id = page_id
    b.block_type = block_type
    b.coverage_score = coverage_score
    b.section_screenshot_url = screenshot_url
    b.ai_processed = ai_processed
    b.content_json = content_json or {"raw_html": f"<section>block{id}</section>"}
    return b


def _project() -> MagicMock:
    p = MagicMock()
    p.id = 42
    return p


def _page(
    page_id: int = 100,
    html: str = "<html>x</html>",
    css_extracted: str | None = "body{color:red}",
) -> MagicMock:
    p = MagicMock()
    p.id = page_id
    p.html_clean = html
    p.css_extracted = css_extracted
    return p


def _setup_ctx(fake_session: MagicMock, *, candidates: list, pages: list = None) -> AgentContext:
    """Configura `fake_session` para distinguir entre Project y ScrapedPage.

    `_apply_raw_html` llama `session.get(ScrapedPage, page_id)` para
    leer `css_extracted`. Mockeamos por tipo de modelo solicitado.
    """
    pages = pages or []
    pages_by_id = {p.id: p for p in pages}
    project = _project()

    def get_side_effect(model, pk):
        name = getattr(model, "__name__", type(model).__name__)
        if name == "Project":
            return project
        if name == "ScrapedPage":
            return pages_by_id.get(pk)
        return None

    fake_session.get.side_effect = get_side_effect

    res_cb = MagicMock()
    res_cb.scalars.return_value = iter(candidates)
    res_sp = MagicMock()
    res_sp.scalars.return_value = iter(pages)
    fake_session.execute.side_effect = [res_cb, res_sp]
    return AgentContext(session=fake_session, project_id=42)


def _fake_http(*, status: int = 200, content: bytes = b"PNG_BYTES") -> MagicMock:
    http = MagicMock()
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    http.get = AsyncMock(return_value=resp)
    http.aclose = AsyncMock()
    return http


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(AiAssistError, match="project_id"):
        AiAssistAgent().run(AgentContext(session=fake_session))


def test_sin_candidatos_skipped(fake_session) -> None:
    """0 bloques candidatos → outputs skipped + reason."""
    ctx = _setup_ctx(fake_session, candidates=[])
    result = AiAssistAgent().run(ctx)
    assert result.outputs["candidates"] == 0
    assert result.outputs["skipped"] is True


def test_sin_api_key_marca_todos_raw(fake_session, monkeypatch) -> None:
    """Sin ANTHROPIC_API_KEY → todos los candidatos van a RAW_HTML."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    candidates = [_block(id=1), _block(id=2), _block(id=3)]
    ctx = _setup_ctx(fake_session, candidates=candidates)

    result = AiAssistAgent().run(ctx)

    assert result.outputs["raw_html"] == 3
    assert result.outputs["ai_generated"] == 0
    assert result.outputs["skipped_api"] is True
    for b in candidates:
        # v0.23.0 — fallback ya no es RAW_HTML; es UNKNOWN + ResidualTask.
        assert b.block_type == BlockType.UNKNOWN
        assert b.ai_processed is True


# ---------- _load_candidates filtros ----------


def test_filtra_unknown_y_coverage_bajo() -> None:
    """Candidatos: UNKNOWN OR coverage<0.6. NO incluye otros tipos con
    coverage alto."""
    blocks = [
        _block(id=1, block_type=BlockType.UNKNOWN, coverage_score=None),
        _block(id=2, block_type=BlockType.HERO, coverage_score=0.3),
        _block(id=3, block_type=BlockType.TEXT, coverage_score=0.9),
        _block(id=4, block_type=BlockType.HEADING, coverage_score=None),
    ]
    fake_session = MagicMock()
    fake_session.execute.return_value.scalars.return_value = iter(blocks)

    agent = AiAssistAgent()
    candidates = agent._load_candidates(
        AgentContext(session=fake_session, project_id=42), 42
    )
    ids = [c.id for c in candidates]
    assert 1 in ids  # UNKNOWN
    assert 2 in ids  # coverage 0.3 < 0.6
    assert 3 not in ids  # coverage 0.9 OK
    assert 4 not in ids  # HEADING ok sin score


def test_filtra_ai_processed_true_excluye() -> None:
    """Bloques ya procesados antes (ai_processed=True) NO se vuelven a tocar."""
    blocks = [
        _block(id=1, block_type=BlockType.UNKNOWN, ai_processed=True),
        _block(id=2, block_type=BlockType.UNKNOWN, ai_processed=False),
    ]
    fake_session = MagicMock()
    # SQL filtra a nivel BD por `ai_processed.is_(False)` → solo bloque 2.
    fake_session.execute.return_value.scalars.return_value = iter([blocks[1]])

    agent = AiAssistAgent()
    candidates = agent._load_candidates(
        AgentContext(session=fake_session, project_id=42), 42
    )
    assert [c.id for c in candidates] == [2]


# ---------- resolve helpers ----------


def test_resolve_threshold_default() -> None:
    assert AiAssistAgent()._resolve_threshold() == DEFAULT_COVERAGE_THRESHOLD


def test_resolve_threshold_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WCM_AI_COVERAGE_THRESHOLD", "0.75")
    assert AiAssistAgent()._resolve_threshold() == 0.75


def test_resolve_budget_default() -> None:
    assert AiAssistAgent()._resolve_budget() == DEFAULT_BUDGET_USD


def test_resolve_budget_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WCM_AI_BUDGET_USD_PER_PROJECT", "25.5")
    assert AiAssistAgent()._resolve_budget() == 25.5


def test_resolve_concurrency_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WCM_AI_CONCURRENCY", "3")
    assert AiAssistAgent()._resolve_concurrency() == 3


def test_resolve_concurrency_env_fuera_rango_cae_a_default(monkeypatch) -> None:
    monkeypatch.setenv("WCM_AI_CONCURRENCY", "100")
    # 100 fuera de [1,20] → DEFAULT_CONCURRENCY (v0.23.0: bajado a 2).
    from wcm_worker.agents.ai_assist import DEFAULT_CONCURRENCY

    assert AiAssistAgent()._resolve_concurrency() == DEFAULT_CONCURRENCY
    assert DEFAULT_CONCURRENCY == 2


def test_resolve_max_blocks_default() -> None:
    """Default cap 30 — protege del rate-limit Anthropic en tiers bajos."""
    from wcm_worker.agents.ai_assist import DEFAULT_MAX_BLOCKS

    assert AiAssistAgent()._resolve_max_blocks() == DEFAULT_MAX_BLOCKS
    assert DEFAULT_MAX_BLOCKS == 30


def test_resolve_max_blocks_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WCM_AI_MAX_BLOCKS_PER_PROJECT", "10")
    assert AiAssistAgent()._resolve_max_blocks() == 10


def test_resolve_max_blocks_env_zero_significa_sin_limite(monkeypatch) -> None:
    """0 desactiva el cap (sin límite)."""
    monkeypatch.setenv("WCM_AI_MAX_BLOCKS_PER_PROJECT", "0")
    assert AiAssistAgent()._resolve_max_blocks() == 0


def test_e2e_cap_max_blocks_difiere_resto_a_raw(fake_session, monkeypatch) -> None:
    """Si len(candidates) > max_blocks → primeros max_blocks van a AI,
    el resto se marca RAW_HTML directamente con reason='deferred_by_cap'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("WCM_AI_MAX_BLOCKS_PER_PROJECT", "2")

    client = MagicMock()
    client.transpile_section = AsyncMock(
        return_value=ClaudeVisionResult(
            elements=[
                {"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}}
            ],
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            model="claude-sonnet-4-6",
        )
    )
    # 5 candidatos UNKNOWN → cap=2 procesa 2, difiere 3 a RAW.
    candidates = [_block(id=i) for i in range(1, 6)]
    ctx = _setup_ctx(fake_session, candidates=candidates, pages=[_page()])
    agent = AiAssistAgent(client=client, http_client=_fake_http())

    result = agent.run(ctx)

    assert result.outputs["ai_generated"] == 2
    # 3 diferidos por cap quedan RAW_HTML. raw_html cuenta solo los del
    # batch principal (los diferidos se marcan antes), pero ai_processed
    # debe ser True en TODOS.
    for b in candidates:
        assert b.ai_processed is True
    # v0.23.0 — los excedentes ya no son RAW_HTML, sino UNKNOWN
    # (ResidualTask con captura). El cap sigue funcionando.
    for b in candidates[2:]:
        assert b.block_type == BlockType.UNKNOWN


# ---------- apply helpers ----------


def test_apply_raw_html_alias_a_unresolved(fake_session) -> None:
    """v0.23.0 — `_apply_raw_html` ahora es alias de `_apply_unresolved`.
    NO emite RAW_HTML; marca UNKNOWN + crea ResidualTask con captura."""
    block = _block(content_json={"raw_html": "<section>hello</section>"})
    block.section_screenshot_url = "https://r2/section-42.png"

    agent = AiAssistAgent()
    agent._apply_raw_html(
        AgentContext(session=fake_session, project_id=42), block, reason="x"
    )
    assert block.block_type == BlockType.UNKNOWN
    assert block.ai_processed is True
    assert block.content_json["raw_html"] == "<section>hello</section>"
    assert block.content_json["_unresolved_reason"] == "x"
    assert block.content_json["_screenshot_url"] == "https://r2/section-42.png"
    # Debe haber añadido el block + 1 ResidualTask a la session.
    added_tasks = [
        c.args[0] for c in fake_session.add.call_args_list
        if type(c.args[0]).__name__ == "ResidualTask"
    ]
    assert len(added_tasks) == 1
    task = added_tasks[0]
    assert task.project_id == block.project_id
    assert task.section_screenshot_url == "https://r2/section-42.png"


def test_apply_unresolved_sin_screenshot_url(fake_session) -> None:
    """Bloque sin screenshot crea residual igualmente (sin captura)."""
    block = _block(content_json={"raw_html": "<section>x</section>"})
    block.section_screenshot_url = None

    agent = AiAssistAgent()
    agent._apply_unresolved(
        AgentContext(session=fake_session, project_id=42), block, reason="ai_failed"
    )
    assert block.block_type == BlockType.UNKNOWN
    assert block.content_json["_screenshot_url"] is None


def test_apply_ai_generated_marca_block(fake_session) -> None:
    block = _block()
    agent = AiAssistAgent()
    elements = [{"id": "abc001", "name": "section", "parent": "0", "settings": {}}]
    agent._apply_ai_generated(
        AgentContext(session=fake_session, project_id=42),
        block,
        elements=elements,
        notes="reproduced",
    )
    assert block.block_type == BlockType.AI_GENERATED
    assert block.content_json["bricks_elements"] == elements
    assert block.content_json["notes"] == "reproduced"
    assert block.ai_processed is True


# ---------- e2e con mock client ----------


def test_e2e_happy_path_marca_ai_generated(fake_session, monkeypatch) -> None:
    """Cliente devuelve elementos válidos → bloque marcado AI_GENERATED."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    elements = [
        {"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}}
    ]
    client = MagicMock()
    client.transpile_section = AsyncMock(
        return_value=ClaudeVisionResult(
            elements=elements,
            notes="",
            tokens_in=1000,
            tokens_out=300,
            cost_usd=0.008,
            model="claude-sonnet-4-6",
        )
    )
    block = _block(id=1, block_type=BlockType.UNKNOWN)
    ctx = _setup_ctx(fake_session, candidates=[block], pages=[_page()])
    agent = AiAssistAgent(client=client, http_client=_fake_http())

    result = agent.run(ctx)

    assert result.outputs["ai_generated"] == 1
    assert result.outputs["raw_html"] == 0
    assert result.outputs["cost_usd"] == 0.008
    assert block.block_type == BlockType.AI_GENERATED


def test_e2e_claude_falla_fallback_raw(fake_session, monkeypatch) -> None:
    """Cliente lanza ClaudeVisionApiError → fallback RAW_HTML."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    client = MagicMock()
    client.transpile_section = AsyncMock(
        side_effect=ClaudeVisionApiError("503 service down"),
    )
    block = _block(id=1, block_type=BlockType.UNKNOWN)
    ctx = _setup_ctx(fake_session, candidates=[block], pages=[_page()])
    agent = AiAssistAgent(client=client, http_client=_fake_http())

    result = agent.run(ctx)

    assert result.outputs["ai_generated"] == 0
    assert result.outputs["raw_html"] == 1
    # v0.23.0 — block_type=UNKNOWN (RAW_HTML deprecado, no se emite).
    assert block.block_type == BlockType.UNKNOWN


def test_e2e_auth_error_aborta_y_marca_resto_raw(fake_session, monkeypatch) -> None:
    """401 en cualquier bloque → abort + resto a RAW_HTML."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
    client = MagicMock()
    client.transpile_section = AsyncMock(
        side_effect=ClaudeVisionAuthError("401"),
    )
    blocks = [_block(id=i) for i in range(1, 4)]
    ctx = _setup_ctx(fake_session, candidates=blocks, pages=[_page()])
    agent = AiAssistAgent(client=client, http_client=_fake_http())

    result = agent.run(ctx)

    assert result.outputs.get("aborted_auth") is True
    # v0.23.0 — Todos los blocks marcados como UNKNOWN + ResidualTask.
    for b in blocks:
        assert b.block_type == BlockType.UNKNOWN
        assert b.ai_processed is True


def test_e2e_screenshot_404_fallback_raw(fake_session, monkeypatch) -> None:
    """Screenshot URL devuelve 404 → fallback RAW sin llamar Claude."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    client = MagicMock()
    client.transpile_section = AsyncMock()
    block = _block(id=1, screenshot_url="https://r2/missing.png")
    ctx = _setup_ctx(fake_session, candidates=[block], pages=[_page()])
    http = _fake_http(status=404)
    agent = AiAssistAgent(client=client, http_client=http)

    result = agent.run(ctx)

    assert result.outputs["raw_html"] == 1
    assert result.outputs["ai_generated"] == 0
    client.transpile_section.assert_not_called()


def test_e2e_sin_screenshot_url_fallback_raw(fake_session, monkeypatch) -> None:
    """Bloque sin section_screenshot_url → fallback RAW sin llamar a R2."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    client = MagicMock()
    client.transpile_section = AsyncMock()
    block = _block(id=1, screenshot_url=None)
    ctx = _setup_ctx(fake_session, candidates=[block], pages=[_page()])
    http = _fake_http()
    agent = AiAssistAgent(client=client, http_client=http)

    result = agent.run(ctx)

    assert result.outputs["raw_html"] == 1
    http.get.assert_not_called()
    client.transpile_section.assert_not_called()
