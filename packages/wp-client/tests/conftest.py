"""Fixtures comunes para tests wp-client."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from wcm_wp_client.config import WpClientConfig


@pytest.fixture()
def fake_config() -> WpClientConfig:
    """Config con valores fake — sirve para construir clientes sin tocar red."""
    return WpClientConfig(
        site_url="https://migrator-sandbox.local",
        rest_user="test",
        rest_app_password="abcd efgh ijkl mnop qrst uvwx",
        verify_ssl=False,
        ssh_host="127.0.0.1",
        ssh_user="alvaro",
        ssh_port=22,
        ssh_key_path="/Users/alvaro/.ssh/id_ed25519",
        wp_path="/Users/alvaro/Local Sites/migrator-sandbox/app/public",
        wpcli_path="/Users/alvaro/Local Sites/migrator-sandbox/app/wp-cli.phar",
        local_php_bin=(
            "/Users/alvaro/Library/Application Support/Local/"
            "lightning-services/php-8.2.29+0/bin/darwin-arm64/bin/php"
        ),
        local_mysql_socket=(
            "/Users/alvaro/Library/Application Support/Local/"
            "run/H1F_xStai/mysql/mysqld.sock"
        ),
    )


def _has_real_sandbox_env() -> bool:
    """Detecta si el .env real está cargado para tests integración."""
    return bool(os.environ.get("WP_DEFAULT_REST_APP_PASSWORD"))


@pytest.fixture()
def real_config_or_skip() -> WpClientConfig:
    """Config leída del entorno real. Skip si no está disponible."""
    if not _has_real_sandbox_env():
        pytest.skip("WP_DEFAULT_REST_APP_PASSWORD no definida; saltando integración")
    return WpClientConfig.from_env()
