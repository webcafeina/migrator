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


def test_bricks_import_content_via_wp_eval_y_fichero_temp(fake_config: WpClientConfig) -> None:
    """Fix 2026-05-20: bricks_import_content sube el JSON a /tmp por SSH
    (cat > path con stdin) y luego usa `wp eval` con file_get_contents +
    update_post_meta. Evita los problemas de:
    - argv > MAX_ARG_STRLEN para JSONs grandes
    - `-` no funciona como value-from-stdin en `wp post meta update`
      (lo guarda literal como string)
    """
    import asyncio
    from unittest.mock import MagicMock

    client = WpCliSshClient(fake_config)

    captured: list[dict] = []

    def _fake_exec_command(cmd: str, timeout=None):
        rec = {"cmd": cmd, "stdin": ""}
        captured.append(rec)
        stdin_mock = MagicMock()
        stdout_mock = MagicMock()
        stdout_mock.channel.recv_exit_status = MagicMock(return_value=0)
        stdout_mock.read = MagicMock(return_value=b"")
        stderr_mock = MagicMock()
        stderr_mock.read = MagicMock(return_value=b"")

        def _write(data):
            rec["stdin"] += data
        stdin_mock.write = _write
        stdin_mock.flush = MagicMock()
        stdin_mock.channel.shutdown_write = MagicMock()
        return stdin_mock, stdout_mock, stderr_mock

    fake_ssh = MagicMock()
    fake_ssh.exec_command = _fake_exec_command
    client._ssh = fake_ssh
    asyncio.run(
        client.bricks_import_content(
            42, [{"id": "section1", "name": "section"}, {"id": "t1", "name": "text"}]
        )
    )

    # Esperamos 3 comandos: cat > /tmp/file, wp eval ..., rm -f.
    assert len(captured) == 3, f"se esperaban 3 comandos, vinieron {len(captured)}"

    # 1. cat > /tmp/wcm-bricks-42-<ts>.json con el JSON por stdin.
    cmd1 = captured[0]["cmd"]
    assert cmd1.startswith("cat >")
    assert "/tmp/wcm-bricks-42-" in cmd1
    assert '"section1"' in captured[0]["stdin"]
    assert '"name": "text"' in captured[0]["stdin"]

    # 2. wp eval con PHP que lee el fichero y actualiza el meta.
    cmd2 = captured[1]["cmd"]
    assert "eval" in cmd2
    assert "file_get_contents" in cmd2
    assert "update_post_meta(42" in cmd2
    assert "_bricks_page_content_2" in cmd2

    # 3. rm -f cleanup del fichero temp.
    cmd3 = captured[2]["cmd"]
    assert cmd3.startswith("rm -f")
    assert "/tmp/wcm-bricks-42-" in cmd3
