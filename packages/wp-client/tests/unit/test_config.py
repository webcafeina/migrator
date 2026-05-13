"""Tests de WpClientConfig."""

from __future__ import annotations

import pytest

from wcm_wp_client.config import WpClientConfig


def test_from_env_complete() -> None:
    env = {
        "WP_DEFAULT_SITE_URL": "https://example.test/",
        "WP_DEFAULT_REST_USER": "admin",
        "WP_DEFAULT_REST_APP_PASSWORD": "abcd efgh",
        "WP_VERIFY_SSL": "false",
        "WP_DEFAULT_HOST": "127.0.0.1",
        "WP_DEFAULT_SSH_USER": "alvaro",
        "WP_DEFAULT_SSH_PORT": "22",
        "WP_DEFAULT_SSH_KEY_PATH": "~/.ssh/id_ed25519",
        "WP_PATH": "/var/www/site",
        "WP_DEFAULT_WPCLI_PATH": "/usr/local/bin/wp",
    }
    cfg = WpClientConfig.from_env(env=env)
    assert cfg.site_url == "https://example.test"  # trailing / removed
    assert cfg.rest_user == "admin"
    assert cfg.verify_ssl is False
    assert cfg.ssh_port == 22
    assert cfg.ssh_key_path.endswith(".ssh/id_ed25519")
    assert "~" not in cfg.ssh_key_path  # expanded


def test_from_env_missing_required_raises() -> None:
    with pytest.raises(ValueError, match="WP_DEFAULT_SITE_URL"):
        WpClientConfig.from_env(env={})


def test_normalized_app_password_strips_spaces() -> None:
    cfg = WpClientConfig(
        site_url="x", rest_user="u", rest_app_password="abcd efgh ijkl",
        verify_ssl=True,
        ssh_host="x", ssh_user="x", ssh_port=22, ssh_key_path="/x",
        wp_path="/x", wpcli_path="/x",
    )
    assert cfg.normalized_app_password == "abcdefghijkl"


def test_rest_endpoint_includes_wp_json() -> None:
    cfg = WpClientConfig(
        site_url="https://example.test", rest_user="u", rest_app_password="p",
        verify_ssl=True,
        ssh_host="x", ssh_user="x", ssh_port=22, ssh_key_path="/x",
        wp_path="/x", wpcli_path="/x",
    )
    assert cfg.rest_endpoint == "https://example.test/wp-json"


def test_verify_ssl_default_true() -> None:
    env = {
        "WP_DEFAULT_SITE_URL": "https://example.test",
        "WP_DEFAULT_REST_USER": "u",
        "WP_DEFAULT_REST_APP_PASSWORD": "p",
        "WP_DEFAULT_HOST": "x",
        "WP_DEFAULT_SSH_USER": "u",
        "WP_DEFAULT_SSH_KEY_PATH": "/x",
        "WP_PATH": "/x",
        "WP_DEFAULT_WPCLI_PATH": "/x",
    }
    cfg = WpClientConfig.from_env(env=env)
    assert cfg.verify_ssl is True
