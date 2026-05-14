"""Tests del rate limiter por dominio."""

from __future__ import annotations

import pytest

from wcm_scraper_core.rate_limit import (
    DomainCooledDownError,
    DomainRateLimiter,
    domain_of,
)


def test_domain_extraction() -> None:
    assert domain_of("https://example.com/path") == "example.com"
    assert domain_of("http://SUB.EXAMPLE.COM/x") == "sub.example.com"
    assert domain_of("not a url") == ""


@pytest.mark.asyncio
async def test_acquire_uses_jitter() -> None:
    limiter = DomainRateLimiter(min_delay_s=0.0, max_delay_s=0.0)
    await limiter.acquire("https://example.com/")
    await limiter.acquire("https://example.com/x")  # no delay porque min/max=0


@pytest.mark.asyncio
async def test_report_blocked_accumulates_and_cools_down() -> None:
    limiter = DomainRateLimiter(
        min_delay_s=0.0, max_delay_s=0.0,
        block_threshold=3, cooldown_s=10,
    )
    url = "https://blocked.example/"
    for _ in range(3):
        limiter.report_blocked(url, 429)
    assert limiter.is_cooled_down(url)

    with pytest.raises(DomainCooledDownError):
        await limiter.acquire(url)


@pytest.mark.asyncio
async def test_other_domains_unaffected_by_one_cooldown() -> None:
    limiter = DomainRateLimiter(
        min_delay_s=0.0, max_delay_s=0.0, block_threshold=2, cooldown_s=10,
    )
    for _ in range(2):
        limiter.report_blocked("https://blocked.example/", 429)
    # Otro dominio sigue accesible
    await limiter.acquire("https://other.example/")


def test_block_below_threshold_no_cooldown() -> None:
    limiter = DomainRateLimiter(block_threshold=3, cooldown_s=10)
    limiter.report_blocked("https://x.com/", 403)
    limiter.report_blocked("https://x.com/", 403)
    assert not limiter.is_cooled_down("https://x.com/")


def test_non_blocking_status_codes_ignored() -> None:
    limiter = DomainRateLimiter(block_threshold=1, cooldown_s=10)
    limiter.report_blocked("https://x.com/", 200)
    limiter.report_blocked("https://x.com/", 404)
    assert not limiter.is_cooled_down("https://x.com/")


def test_reset_cooldown() -> None:
    limiter = DomainRateLimiter(block_threshold=1, cooldown_s=10)
    limiter.report_blocked("https://x.com/", 429)
    assert limiter.is_cooled_down("https://x.com/")
    limiter.reset_cooldown("https://x.com/")
    assert not limiter.is_cooled_down("https://x.com/")
