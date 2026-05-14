"""Configuración del cliente WP, normalmente cargada desde .env.

`WpClientConfig.from_env()` lee env vars con prefijo `WP_DEFAULT_*`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WpClientConfig:
    """Config inmutable. Una instancia por sandbox/proyecto.

    - REST: usa `site_url` + `rest_user` + `rest_app_password` (basic auth).
    - SSH/CLI: usa `ssh_host/user/port/key_path` + `wp_path` + `wpcli_path`.
    - Entorno Local (dev): `local_php_bin` + `local_mysql_socket` resuelven
      las particularidades de Local by Flywheel. En producción real (WHM)
      ambos son None y se usa `wp` binario global con DB accesible normal.
    """

    site_url: str
    rest_user: str
    rest_app_password: str
    verify_ssl: bool

    ssh_host: str
    ssh_user: str
    ssh_port: int
    ssh_key_path: str
    wp_path: str
    wpcli_path: str

    local_php_bin: str | None = None
    local_mysql_socket: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> WpClientConfig:
        e = env if env is not None else os.environ

        def _req(name: str) -> str:
            v = e.get(name)
            if not v:
                raise ValueError(f"WpClientConfig: env var {name} requerida pero vacía")
            return v

        def _expand(path: str) -> str:
            return os.path.expanduser(path) if path.startswith("~") else path

        return cls(
            site_url=_req("WP_DEFAULT_SITE_URL").rstrip("/"),
            rest_user=_req("WP_DEFAULT_REST_USER"),
            rest_app_password=_req("WP_DEFAULT_REST_APP_PASSWORD"),
            verify_ssl=e.get("WP_VERIFY_SSL", "true").lower() not in ("0", "false", "no"),
            ssh_host=_req("WP_DEFAULT_HOST"),
            ssh_user=_req("WP_DEFAULT_SSH_USER"),
            ssh_port=int(e.get("WP_DEFAULT_SSH_PORT", "22")),
            ssh_key_path=_expand(_req("WP_DEFAULT_SSH_KEY_PATH")),
            wp_path=_req("WP_PATH"),
            wpcli_path=_req("WP_DEFAULT_WPCLI_PATH"),
            local_php_bin=e.get("WP_LOCAL_PHP_BIN") or None,
            local_mysql_socket=e.get("WP_LOCAL_MYSQL_SOCKET") or None,
        )

    @property
    def rest_endpoint(self) -> str:
        return f"{self.site_url}/wp-json"

    @property
    def normalized_app_password(self) -> str:
        """WordPress acepta Application Passwords con o sin espacios.
        Las normalizamos a sin espacios para uso programático.
        """
        return self.rest_app_password.replace(" ", "")
