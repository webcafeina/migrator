"""Cliente WP-CLI vía SSH (paramiko).

Skill: `wpcli-ssh`. Cuándo usar este vs WpRestClient:
- N > 100 items → WP-CLI gana.
- Operaciones que tocan filesystem (core install, plugin install,
  search-replace de DB) → WP-CLI.
- Operaciones que el REST no expone → WP-CLI.

Sandbox local (Local by Flywheel) tiene particularidades:
- PHP no está en PATH del SSH no-interactivo → invocar binario absoluto
  (`local_php_bin` en la config).
- MySQL escucha en socket Unix con ID volátil → pasar
  `-d mysqli.default_socket=<sock>` a PHP.
- `wp` binario global no existe → usar `php wp-cli.phar`.

En producción WHM/cPanel real, `wp` está en PATH y la DB en localhost:3306
estándar; entonces `local_php_bin` y `local_mysql_socket` son None y el
cliente construye comandos `wp --path=...` directamente.
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass
from typing import Any

import paramiko

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.errors import (
    WpCliExecutionError,
    WpSshAuthError,
    WpSshConnectionError,
)

log = logging.getLogger("wcm.wp_client.ssh_cli")


@dataclass
class WpCliResult:
    exit_code: int
    stdout: str
    stderr: str
    command: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class WpCliSshClient:
    """Cliente SSH + WP-CLI. Context manager para conexión paramiko.

    Uso:
        async with WpCliSshClient(cfg) as cli:
            res = await cli.run(["option", "get", "siteurl"])
            print(res.stdout)
    """

    def __init__(
        self,
        config: WpClientConfig,
        *,
        default_timeout_s: float = 60.0,
        known_hosts_strict: bool = False,
    ) -> None:
        self.config = config
        self._default_timeout_s = default_timeout_s
        self._known_hosts_strict = known_hosts_strict
        self._ssh: paramiko.SSHClient | None = None

    async def __aenter__(self) -> "WpCliSshClient":
        client = paramiko.SSHClient()
        if self._known_hosts_strict:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            # En sandbox local (127.0.0.1) la verificación strict no aporta.
            # En producción cambiar known_hosts_strict=True.
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.config.ssh_host,
                port=self.config.ssh_port,
                username=self.config.ssh_user,
                key_filename=self.config.ssh_key_path,
                timeout=10.0,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException as e:
            raise WpSshAuthError(
                f"SSH auth failed for {self.config.ssh_user}@{self.config.ssh_host}: {e}"
            ) from e
        except (paramiko.SSHException, OSError) as e:
            raise WpSshConnectionError(
                f"SSH connect failed to {self.config.ssh_host}:{self.config.ssh_port}: {e}"
            ) from e
        self._ssh = client
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    @property
    def _client(self) -> paramiko.SSHClient:
        if self._ssh is None:
            raise RuntimeError("WpCliSshClient: usar como `async with WpCliSshClient(cfg)`")
        return self._ssh

    # ---------- command building ----------

    def _build_wpcli_cmd(self, args: list[str]) -> str:
        """Construye la línea de comando WP-CLI completa, escapada correctamente.

        Aplica los workarounds de Local (PHP absoluto + socket mysql) si
        están configurados.
        """
        parts: list[str] = []

        if self.config.local_php_bin and self.config.wpcli_path.endswith(".phar"):
            parts.append(shlex.quote(self.config.local_php_bin))
            if self.config.local_mysql_socket:
                parts.append("-d")
                parts.append(
                    f"mysqli.default_socket={shlex.quote(self.config.local_mysql_socket)}"
                )
            parts.append(shlex.quote(self.config.wpcli_path))
        elif self.config.wpcli_path.endswith(".phar"):
            # PHP en PATH + phar
            parts.append("php")
            parts.append(shlex.quote(self.config.wpcli_path))
        else:
            # wp binario global
            parts.append(shlex.quote(self.config.wpcli_path))

        parts.append(f"--path={shlex.quote(self.config.wp_path)}")
        parts.extend(shlex.quote(a) for a in args)
        return " ".join(parts)

    # ---------- exec ----------

    async def run(
        self,
        args: list[str],
        *,
        timeout_s: float | None = None,
        stdin_input: str | None = None,
    ) -> WpCliResult:
        """Ejecuta `wp <args>` en el destino. Bloquea hasta finalizar.

        No reintenta automáticamente; el caller decide (algunos comandos
        son destructivos y nunca queremos retry, otros transitorios sí).
        """
        cmd = self._build_wpcli_cmd(args)
        timeout = timeout_s if timeout_s is not None else self._default_timeout_s
        log.debug("ssh_exec", extra={"cmd": cmd, "timeout_s": timeout})

        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)
        if stdin_input is not None:
            stdin.write(stdin_input)
            stdin.flush()
            stdin.channel.shutdown_write()

        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return WpCliResult(exit_code=exit_code, stdout=out, stderr=err, command=cmd)

    async def run_or_raise(self, args: list[str], **kwargs: Any) -> WpCliResult:
        """Como `run` pero levanta WpCliExecutionError si exit_code != 0."""
        result = await self.run(args, **kwargs)
        if not result.ok:
            raise WpCliExecutionError(
                f"wp {' '.join(args)} → exit {result.exit_code}",
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                command=result.command,
            )
        return result

    # ---------- high-level helpers ----------

    async def core_version(self) -> str:
        r = await self.run_or_raise(["core", "version"])
        return r.stdout.strip()

    async def core_is_installed(self) -> bool:
        r = await self.run(["core", "is-installed"])
        return r.ok

    async def option_get(self, key: str) -> str:
        r = await self.run_or_raise(["option", "get", key])
        return r.stdout.strip()

    async def option_update(self, key: str, value: Any, *, format: str = "plaintext") -> None:
        """Actualiza una option. Para JSON, pasar dict/list y `format="json"`."""
        if format == "json":
            payload = json.dumps(value, ensure_ascii=False)
            await self.run_or_raise(
                ["option", "update", key, payload, "--format=json"]
            )
        else:
            await self.run_or_raise(["option", "update", key, str(value)])

    async def plugin_install(
        self, slug_or_path: str, *, activate: bool = True, version: str | None = None
    ) -> None:
        args = ["plugin", "install", slug_or_path]
        if version is not None:
            args.append(f"--version={version}")
        if activate:
            args.append("--activate")
        await self.run_or_raise(args, timeout_s=180.0)

    async def plugin_is_active(self, slug: str) -> bool:
        r = await self.run(["plugin", "is-active", slug])
        return r.ok

    async def theme_install(
        self, slug_or_path: str, *, activate: bool = True, version: str | None = None
    ) -> None:
        args = ["theme", "install", slug_or_path]
        if version is not None:
            args.append(f"--version={version}")
        if activate:
            args.append("--activate")
        await self.run_or_raise(args, timeout_s=180.0)

    async def search_replace(
        self,
        old: str,
        new: str,
        *,
        tables: list[str] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Search-replace en la BD.

        `dry_run=True` por defecto — operación destructiva, exigir
        confirmación explícita pasando dry_run=False.

        Devuelve `{"dry_run": bool, "replacements": int}`. WP-CLI
        search-replace solo admite `--format=count` para output máquina-
        parseable (no acepta `--format=json` como otros comandos).
        """
        args = ["search-replace", old, new]
        if tables:
            args.append(",".join(tables))
        if dry_run:
            args.append("--dry-run")
        args.append("--format=count")
        r = await self.run_or_raise(args, timeout_s=300.0)
        try:
            replacements = int(r.stdout.strip())
        except ValueError:
            replacements = 0
        return {"dry_run": dry_run, "replacements": replacements}

    async def bricks_import_content(
        self, post_id: int, bricks_json: list[dict[str, Any]]
    ) -> None:
        """Inyecta el contenido Bricks vía wp post meta update con --format=json.

        Es la vía RECOMENDADA para Bricks pages grandes (>500 elementos);
        el REST API puede atragantarse con payloads de varios MB.
        """
        payload = json.dumps(bricks_json, ensure_ascii=False)
        await self.run_or_raise(
            [
                "post", "meta", "update",
                str(post_id), "_bricks_page_content_2", payload,
                "--format=json",
            ],
            timeout_s=180.0,
        )

    async def post_create(self, payload: dict[str, Any]) -> int:
        """Crea un post/page vía WP-CLI (alternativa a REST).

        Devuelve el post ID. Usa `--porcelain` para stdout limpio.
        """
        args = ["post", "create"]
        for key, value in payload.items():
            if key == "post_content":
                # contenido largo: vía stdin
                continue
            args.append(f"--{key.replace('_', '-')}={value}")
        args.append("--porcelain")

        stdin_input = payload.get("post_content")
        if stdin_input:
            args.append("-")  # leer post_content de stdin
        r = await self.run_or_raise(args, stdin_input=stdin_input, timeout_s=120.0)
        return int(r.stdout.strip())
