"""Tests del proxy rotator y backends."""

from __future__ import annotations

from wcm_scraper_core.proxy import (
    BrightDataBackend,
    NoProxyBackend,
    ScraperApiBackend,
    WebshareBackend,
    build_default_rotator,
)


def test_noproxy_always_available() -> None:
    backend = NoProxyBackend()
    assert backend.is_available()
    assert backend.next_proxy() is None


def test_webshare_builds_proxy_url() -> None:
    backend = WebshareBackend(username="user1", password="pwd")
    cfg = backend.next_proxy()
    assert cfg is not None
    assert "user1:pwd" in cfg.url
    assert "p.webshare.io:80" in cfg.url


def test_webshare_sticky_session_uses_slot_suffix() -> None:
    backend = WebshareBackend(username="user1", password="pwd")
    cfg = backend.next_proxy(sticky_key="dominio.com")
    assert cfg is not None
    # Debe contener user1-<n>
    assert "user1-" in cfg.url


def test_scraperapi_builds_proxy_url() -> None:
    backend = ScraperApiBackend(api_key="abc123")
    cfg = backend.next_proxy()
    assert cfg is not None
    assert "scraperapi:abc123" in cfg.url
    assert "proxy-server.scraperapi.com:8001" in cfg.url


def test_brightdata_builds_proxy_url() -> None:
    backend = BrightDataBackend(customer_id="cid", zone="res", password="pwd")
    cfg = backend.next_proxy()
    assert cfg is not None
    assert "cid-zone-res:pwd" in cfg.url
    assert "brd.superproxy.io:22225" in cfg.url


def test_default_rotator_uses_noproxy_in_dev() -> None:
    rotator = build_default_rotator(env={"ENV": "development"})
    assert rotator.current_backend().name == "noproxy"


def test_default_rotator_prefers_paid_in_production() -> None:
    env = {
        "ENV": "production",
        "WEBSHARE_USER": "u",
        "WEBSHARE_PASSWORD": "p",
    }
    rotator = build_default_rotator(env=env)
    assert rotator.current_backend().name == "webshare"


def test_default_rotator_escalates_through_tiers() -> None:
    env = {
        "ENV": "production",
        "WEBSHARE_USER": "u",
        "WEBSHARE_PASSWORD": "p",
        "SCRAPERAPI_KEY": "abc",
        "BRIGHTDATA_CUSTOMER_ID": "cid",
        "BRIGHTDATA_ZONE": "res",
        "BRIGHTDATA_PASSWORD": "pwd",
    }
    rotator = build_default_rotator(env=env)
    assert rotator.current_backend().name == "webshare"
    assert rotator.escalate()  # → scraperapi
    assert rotator.current_backend().name == "scraperapi"
    assert rotator.escalate()  # → brightdata
    assert rotator.current_backend().name == "brightdata"
    assert not rotator.escalate()  # no más backends
