"""Tests unit del WpCliSshClient — solo lógica de construcción de comandos
(la conexión real se prueba en tests/integration con sandbox)."""

from __future__ import annotations

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.ssh_cli import WpCliSshClient


def test_build_wpcli_cmd_with_local_php_and_socket(fake_config: WpClientConfig) -> None:
    client = WpCliSshClient(fake_config)
    cmd = client._build_wpcli_cmd(["option", "get", "siteurl"])
    # Debe llevar PHP absoluto + socket + phar absoluto + --path
    assert fake_config.local_php_bin in cmd
    assert "mysqli.default_socket=" in cmd
    assert fake_config.wpcli_path in cmd
    assert f"--path={_quote(fake_config.wp_path)}" in cmd
    assert "option get siteurl" in cmd


def test_build_wpcli_cmd_without_local_uses_php_phar() -> None:
    cfg = WpClientConfig(
        site_url="x", rest_user="u", rest_app_password="p", verify_ssl=True,
        ssh_host="x", ssh_user="u", ssh_port=22, ssh_key_path="/x",
        wp_path="/var/www", wpcli_path="/opt/wp-cli.phar",
        local_php_bin=None, local_mysql_socket=None,
    )
    client = WpCliSshClient(cfg)
    cmd = client._build_wpcli_cmd(["option", "get", "siteurl"])
    # Sin local_php_bin, usa `php` en PATH
    assert cmd.startswith("php ")
    assert "wp-cli.phar" in cmd
    assert "mysqli.default_socket" not in cmd


def test_build_wpcli_cmd_with_wp_binary() -> None:
    cfg = WpClientConfig(
        site_url="x", rest_user="u", rest_app_password="p", verify_ssl=True,
        ssh_host="x", ssh_user="u", ssh_port=22, ssh_key_path="/x",
        wp_path="/var/www", wpcli_path="/usr/local/bin/wp",
        local_php_bin=None, local_mysql_socket=None,
    )
    client = WpCliSshClient(cfg)
    cmd = client._build_wpcli_cmd(["plugin", "list"])
    assert cmd.startswith("/usr/local/bin/wp ")
    assert "php " not in cmd[: cmd.find(" ")]
    assert "plugin list" in cmd


def test_build_wpcli_cmd_escapes_special_chars(fake_config: WpClientConfig) -> None:
    client = WpCliSshClient(fake_config)
    cmd = client._build_wpcli_cmd(["option", "update", "blogname", "Hola 'mundo'"])
    # shlex.quote escapa la comilla simple
    assert "'\\''" in cmd or '"' in cmd or "\\'" in cmd


def _quote(s: str) -> str:
    import shlex

    return shlex.quote(s)
