"""Tests del LLMSectionRanker (v0.28.0 B14)."""

from __future__ import annotations

import pytest

from wcm_bricks_transpiler.redesign.llm_ranker import (
    LLMSectionRanker,
    cache_key,
    candidates_hash,
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _hash_fallback(business_name: str, candidates: list) -> str:
    """Fallback simple para tests — devuelve el primer candidato."""
    return candidates[0]["id"] if candidates else ""


def _candidates(*ids: str) -> list[dict]:
    return [{"id": i, "n_elements": 10, "has_image": True, "has_cta": False} for i in ids]


# -----------------------------------------------------------------------------
# candidates_hash / cache_key — deterministas
# -----------------------------------------------------------------------------


def test_candidates_hash_stable_same_ids() -> None:
    a = _candidates("hero-1", "hero-2", "hero-3")
    b = _candidates("hero-3", "hero-2", "hero-1")  # mismo set, distinto orden
    assert candidates_hash(a) == candidates_hash(b)


def test_candidates_hash_different_ids() -> None:
    a = _candidates("hero-1", "hero-2")
    b = _candidates("hero-1", "hero-3")
    assert candidates_hash(a) != candidates_hash(b)


def test_cache_key_includes_section_index() -> None:
    cands = _candidates("hero-1", "hero-2")
    assert cache_key(0, cands) != cache_key(1, cands)


# -----------------------------------------------------------------------------
# Atajos N=0, N=1
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_raises_with_zero_candidates() -> None:
    async def llm(_b, _s, _c):
        return None
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    with pytest.raises(ValueError):
        await ranker.choose(section_index=0, section_spec={}, candidates=[], brief_context={})


@pytest.mark.asyncio
async def test_choose_short_circuits_with_single_candidate() -> None:
    llm_called = []
    async def llm(_b, _s, _c):
        llm_called.append(1)
        return None
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=_candidates("only-one"), brief_context={},
    )
    assert result.template_id == "only-one"
    assert result.cache_hit is False
    assert result.cost_usd == 0.0
    assert llm_called == []  # nunca se llamó


# -----------------------------------------------------------------------------
# Cache hit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_uses_cache_hit() -> None:
    llm_called = []
    async def llm(_b, _s, _c):
        llm_called.append(1)
        return {"template_id": "hero-1", "rationale": "fresh"}
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2", "hero-3")
    ck = cache_key(0, cands)
    cache = {ck: {"template_id": "hero-2", "rationale": "cached"}}
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={}, cache=cache,
    )
    assert result.template_id == "hero-2"
    assert result.cache_hit is True
    assert result.rationale == "cached"
    assert llm_called == []


@pytest.mark.asyncio
async def test_choose_persists_to_cache_on_miss() -> None:
    async def llm(_b, _s, _c):
        return {"template_id": "hero-2", "rationale": "best", "cost_usd": 0.01}
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2", "hero-3")
    cache: dict = {}
    result = await ranker.choose(
        section_index=5, section_spec={"type": "hero"},
        candidates=cands, brief_context={}, cache=cache,
    )
    assert result.template_id == "hero-2"
    assert result.cache_hit is False
    assert result.cost_usd == 0.01
    # cache se ha mutado in-place con la elección
    ck = cache_key(5, cands)
    assert cache[ck]["template_id"] == "hero-2"


# -----------------------------------------------------------------------------
# LLM happy path
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_returns_llm_valid_id() -> None:
    async def llm(_b, _s, c):
        # Elige el 3er candidato
        return {"template_id": c[2]["id"], "rationale": "best fit", "cost_usd": 0.012}
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2", "hero-3")
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={"business": {"name": "Acme"}},
    )
    assert result.template_id == "hero-3"
    assert result.fallback_used is False
    assert result.rationale == "best fit"


# -----------------------------------------------------------------------------
# Fallback al hash
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_falls_back_when_llm_returns_invalid_id() -> None:
    async def llm(_b, _s, _c):
        return {"template_id": "non-existent-id", "rationale": "..."}
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2")
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={"business": {"name": "Acme"}},
    )
    assert result.fallback_used is True
    assert result.template_id == "hero-1"  # _hash_fallback devuelve el primero


@pytest.mark.asyncio
async def test_choose_falls_back_when_llm_raises() -> None:
    async def llm(_b, _s, _c):
        raise TimeoutError("network down")
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2")
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={"business": {"name": "Acme"}},
    )
    assert result.fallback_used is True
    assert result.template_id == "hero-1"


@pytest.mark.asyncio
async def test_choose_falls_back_when_llm_returns_none() -> None:
    async def llm(_b, _s, _c):
        return None
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2")
    result = await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={"business": {"name": "Acme"}},
    )
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_choose_fallback_does_not_persist_to_cache() -> None:
    """Si caemos al hash, NO se guarda en cache (queremos volver a
    intentar LLM en próximo run cuando funcione)."""
    async def llm(_b, _s, _c):
        raise RuntimeError("transient")
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    cands = _candidates("hero-1", "hero-2")
    cache: dict = {}
    await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=cands, brief_context={"business": {"name": "Acme"}},
        cache=cache,
    )
    assert cache == {}  # no se guarda fallback


# -----------------------------------------------------------------------------
# Subset cuando N > MAX
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_with_many_candidates_sends_subset() -> None:
    """Cuando N > MAX_CANDIDATES_SENT_TO_LLM (30), debe samplear."""
    received_count = []
    async def llm(_b, _s, c):
        received_count.append(len(c))
        return {"template_id": c[0]["id"], "rationale": "..."}
    ranker = LLMSectionRanker(llm_call=llm, hash_fallback=_hash_fallback)
    big = _candidates(*[f"hero-{i:03d}" for i in range(50)])
    await ranker.choose(
        section_index=0, section_spec={"type": "hero"},
        candidates=big, brief_context={},
    )
    assert received_count == [30]
