"""Tests de UserAgentPool y InMemoryCache."""

from __future__ import annotations

import random
import time

from wcm_scraper_core.cache import InMemoryCache
from wcm_scraper_core.ua import STATIC_UA_POOL, UserAgentPool


def test_pool_uses_static_by_default() -> None:
    pool = UserAgentPool()
    ua = pool.next()
    assert ua in STATIC_UA_POOL


def test_pool_with_custom_seed_is_deterministic() -> None:
    rng = random.Random(42)
    pool1 = UserAgentPool(rng=rng)
    rng = random.Random(42)
    pool2 = UserAgentPool(rng=rng)
    assert pool1.next() == pool2.next()


def test_sticky_session_returns_same_ua_per_key() -> None:
    pool = UserAgentPool()
    a = pool.for_session("example.com")
    b = pool.for_session("example.com")
    c = pool.for_session("other.com")
    assert a == b
    # c puede coincidir por azar; reset y verificar que cambia el binding
    pool.reset_session("example.com")
    a2 = pool.for_session("example.com")
    assert a2  # no asserción de inequalidad; pool podría devolver mismo UA


def test_custom_pool_required_non_empty() -> None:
    import pytest

    with pytest.raises(ValueError):
        UserAgentPool(pool=[])


def test_in_memory_cache_set_get() -> None:
    cache = InMemoryCache()
    cache.set("k1", "v1", ttl_seconds=60)
    assert cache.get("k1") == "v1"


def test_in_memory_cache_expires(monkeypatch) -> None:
    cache = InMemoryCache()
    # Capturar el monotonic real ANTES del monkeypatch para evitar recursion
    real_monotonic = time.monotonic
    cache.set("k", "v", ttl_seconds=1)
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 100)
    assert cache.get("k") is None


def test_in_memory_cache_delete() -> None:
    cache = InMemoryCache()
    cache.set("k", "v", ttl_seconds=60)
    cache.delete("k")
    assert cache.get("k") is None
