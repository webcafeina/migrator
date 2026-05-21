"""Tests del ClaudeVisionClient (AI.2 — sprint v0.22.0).

Mocks de la SDK Anthropic — NO se hacen llamadas reales en CI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_worker.errors import (
    ClaudeVisionApiError,
    ClaudeVisionAuthError,
    ClaudeVisionInvalidOutputError,
)
from wcm_worker.integrations.claude_vision import (
    PRICING_USD_PER_MTOK,
    ClaudeVisionClient,
    _compute_cost,
    compute_input_hash,
)


def _fake_tool_use_block(elements: list, notes: str = "") -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = {"elements": elements, "notes": notes}
    return block


def _fake_response(
    elements: list, *, tokens_in: int = 1500, tokens_out: int = 500, notes: str = ""
) -> MagicMock:
    resp = MagicMock()
    resp.content = [_fake_tool_use_block(elements, notes)]
    resp.usage = MagicMock()
    resp.usage.input_tokens = tokens_in
    resp.usage.output_tokens = tokens_out
    return resp


def _fake_sdk_client(response_or_exc) -> MagicMock:
    """Mock del AsyncAnthropic cliente."""
    sdk = MagicMock()
    if isinstance(response_or_exc, Exception):
        sdk.messages.create = AsyncMock(side_effect=response_or_exc)
    else:
        sdk.messages.create = AsyncMock(return_value=response_or_exc)
    return sdk


# ---------- compute_input_hash ----------


def test_input_hash_deterministico() -> None:
    h1 = compute_input_hash(b"png1", "<html>x</html>", "#sel")
    h2 = compute_input_hash(b"png1", "<html>x</html>", "#sel")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_input_hash_cambia_por_screenshot() -> None:
    h1 = compute_input_hash(b"png1", "<html>x</html>", "#sel")
    h2 = compute_input_hash(b"png2", "<html>x</html>", "#sel")
    assert h1 != h2


def test_input_hash_cambia_por_html() -> None:
    h1 = compute_input_hash(b"png", "<html>a</html>", "#sel")
    h2 = compute_input_hash(b"png", "<html>b</html>", "#sel")
    assert h1 != h2


def test_input_hash_cambia_por_selector() -> None:
    h1 = compute_input_hash(b"png", "<html>x</html>", "#a")
    h2 = compute_input_hash(b"png", "<html>x</html>", "#b")
    assert h1 != h2


# ---------- _compute_cost ----------


def test_cost_claude_sonnet_4_6_pricing() -> None:
    # 1500 in × $3/MTok = 0.0045; 500 out × $15/MTok = 0.0075
    cost = _compute_cost("claude-sonnet-4-6", 1500, 500)
    assert round(cost, 6) == 0.012  # 0.0045 + 0.0075


def test_cost_modelo_desconocido_devuelve_cero() -> None:
    """Defensive: si rotamos modelo sin actualizar PRICING, cost=0 antes
    que pretender un valor incorrecto."""
    cost = _compute_cost("claude-future-model-x", 1500, 500)
    assert cost == 0.0


def test_pricing_tiene_sonnet_y_opus() -> None:
    """Sanity: las dos familias del producto deben estar pricied."""
    assert "claude-sonnet-4-6" in PRICING_USD_PER_MTOK
    assert "claude-opus-4-7" in PRICING_USD_PER_MTOK


# ---------- transpile_section happy path ----------


@pytest.mark.asyncio
async def test_transpile_section_happy_path() -> None:
    elements = [
        {"id": "abc001", "name": "section", "parent": "0", "children": ["abc002"], "settings": {}},
        {"id": "abc002", "name": "container", "parent": "abc001", "children": [], "settings": {}},
    ]
    sdk = _fake_sdk_client(_fake_response(elements, tokens_in=1500, tokens_out=500))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk)

    result = await client.transpile_section(
        screenshot_png=b"fake-png",
        html="<section>x</section>",
        selector="#sec1",
        project_id=42,
    )

    assert result.elements == elements
    assert result.tokens_in == 1500
    assert result.tokens_out == 500
    assert result.model == "claude-sonnet-4-6"
    assert round(result.cost_usd, 6) == 0.012
    assert result.cache_hit is False

    # SDK llamado con tool_choice forzado
    call_kwargs = sdk.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"]["name"] == "emit_bricks_elements"


@pytest.mark.asyncio
async def test_transpile_section_html_truncado_si_excede_32kb() -> None:
    """HTML > 32KB se trunca para no quemar tokens."""
    huge_html = "<div>" + ("x" * 40_000) + "</div>"
    elements = [{"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}}]
    sdk = _fake_sdk_client(_fake_response(elements))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk)

    await client.transpile_section(
        screenshot_png=b"png",
        html=huge_html,
        selector="#x",
        project_id=1,
    )
    user_msg = sdk.messages.create.call_args.kwargs["messages"][0]
    text_part = next(p for p in user_msg["content"] if p["type"] == "text")
    assert "TRUNCATED" in text_part["text"]
    assert len(text_part["text"]) < 40_000


# ---------- errores ----------


@pytest.mark.asyncio
async def test_auth_error_no_retry() -> None:
    """401/403 nunca reintenta — fail-fast."""

    class _AuthErr(Exception):
        pass

    _AuthErr.__name__ = "AuthenticationError"
    sdk = _fake_sdk_client(_AuthErr("401 invalid key"))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk, retries=3)

    with pytest.raises(ClaudeVisionAuthError):
        await client.transpile_section(
            screenshot_png=b"png", html="<x/>", selector="#x", project_id=1
        )
    # Solo 1 llamada (no retries).
    assert sdk.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_api_5xx_reintenta_y_falla() -> None:
    sdk = _fake_sdk_client(RuntimeError("503 service unavailable"))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk, retries=3)
    # Patchear asyncio.sleep para no esperar en tests
    import asyncio
    orig_sleep = asyncio.sleep

    async def _no_sleep(_):
        return

    asyncio.sleep = _no_sleep  # type: ignore[assignment]
    try:
        with pytest.raises(ClaudeVisionApiError):
            await client.transpile_section(
                screenshot_png=b"png", html="<x/>", selector="#x", project_id=1
            )
    finally:
        asyncio.sleep = orig_sleep
    # 3 intentos exactos.
    assert sdk.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_response_sin_tool_use_levanta_invalid_output() -> None:
    """Si Claude responde texto libre sin invocar la tool → error explícito."""
    resp = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    resp.content = [text_block]
    resp.usage = MagicMock(input_tokens=100, output_tokens=50)
    sdk = _fake_sdk_client(resp)
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk, retries=1)

    with pytest.raises(ClaudeVisionInvalidOutputError):
        await client.transpile_section(
            screenshot_png=b"png", html="<x/>", selector="#x", project_id=1
        )


@pytest.mark.asyncio
async def test_response_elements_vacio_levanta_invalid_output() -> None:
    sdk = _fake_sdk_client(_fake_response(elements=[]))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk, retries=1)

    with pytest.raises(ClaudeVisionInvalidOutputError):
        await client.transpile_section(
            screenshot_png=b"png", html="<x/>", selector="#x", project_id=1
        )


# ---------- cache ----------


@pytest.mark.asyncio
async def test_cache_hit_no_llama_api() -> None:
    """Si el hash está en ai_section_cache, no se llama al SDK."""
    fake_row = MagicMock()
    fake_row.response_json = {"elements": [{"id": "ca0001", "name": "section", "parent": "0"}], "notes": ""}
    fake_row.tokens_in = 1500
    fake_row.tokens_out = 500
    fake_row.cost_usd = 0.012
    fake_row.model = "claude-sonnet-4-6"

    fake_session = MagicMock()
    fake_session.execute.return_value.scalar_one_or_none.return_value = fake_row

    sdk = _fake_sdk_client(_fake_response([{"id": "new001", "name": "section", "parent": "0"}]))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk)

    result = await client.transpile_section(
        screenshot_png=b"png",
        html="<x/>",
        selector="#x",
        project_id=42,
        session=fake_session,
    )

    assert result.cache_hit is True
    assert result.elements[0]["id"] == "ca0001"  # del cache, no del SDK
    sdk.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_persiste_response() -> None:
    """Si cache miss → API llamada + entry persistida en BD."""
    fake_session = MagicMock()
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    elements = [{"id": "abc001", "name": "section", "parent": "0", "children": [], "settings": {}}]
    sdk = _fake_sdk_client(_fake_response(elements, tokens_in=1000, tokens_out=300))
    client = ClaudeVisionClient(api_key="fake", sdk_client=sdk)

    result = await client.transpile_section(
        screenshot_png=b"png",
        html="<x/>",
        selector="#x",
        project_id=42,
        session=fake_session,
    )

    assert result.cache_hit is False
    sdk.messages.create.assert_called_once()
    # session.add invocado con un AiSectionCache.
    from wcm_db.models.ai_section_cache import AiSectionCache

    added = [c for c in fake_session.add.call_args_list if isinstance(c.args[0], AiSectionCache)]
    assert len(added) == 1
    entry = added[0].args[0]
    assert entry.tokens_in == 1000
    assert entry.tokens_out == 300
