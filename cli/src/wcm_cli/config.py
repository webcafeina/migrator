"""Configuración del CLI + cache de credenciales.

Estrategia:
- `API_URL`: leído de env (con .env autocargado si está en cwd).
- Token: cache local en `~/.config/wcm/credentials.json` con permisos 600.
  Override con env var `WCM_TOKEN` (útil en CI).
- El CLI nunca persiste passwords; solo el JWT emitido por `/auth/login`.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

CREDENTIALS_DIR = Path.home() / ".config" / "wcm"
CREDENTIALS_PATH = CREDENTIALS_DIR / "credentials.json"


@dataclass(frozen=True)
class CliConfig:
    api_url: str
    timeout_s: float = 30.0
    verify_ssl: bool = True

    @classmethod
    def load(cls) -> CliConfig:
        _autoload_dotenv()
        api_url = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
        verify = os.environ.get("WP_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
        timeout = float(os.environ.get("WCM_CLI_TIMEOUT_S", "30"))
        return cls(api_url=api_url, timeout_s=timeout, verify_ssl=verify)


def _autoload_dotenv() -> None:
    """Carga `.env` del cwd si existe y aún no se cargó. Sin dependencia
    externa: parseo manual mínimo (compatible con quoted values).
    """
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # No sobreescribimos lo que ya esté en el entorno
        os.environ.setdefault(key, value)


# ---------- Token cache ----------

def save_token(token: str) -> Path:
    """Guarda el token en `~/.config/wcm/credentials.json` con permisos 600."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.chmod(0o700)
    CREDENTIALS_PATH.write_text(json.dumps({"token": token}), encoding="utf-8")
    CREDENTIALS_PATH.chmod(0o600)
    return CREDENTIALS_PATH


def load_token() -> str | None:
    """Devuelve el token de WCM_TOKEN (prioritario) o del fichero local."""
    if env_token := os.environ.get("WCM_TOKEN"):
        return env_token
    if not CREDENTIALS_PATH.exists():
        return None
    # Comprobación de permisos defensiva: si el fichero es world-readable,
    # mejor no usarlo (riesgo de fuga).
    st = CREDENTIALS_PATH.stat()
    if st.st_mode & (stat.S_IROTH | stat.S_IWOTH | stat.S_IRGRP | stat.S_IWGRP):
        # Reescribir con permisos correctos en lugar de fallar
        CREDENTIALS_PATH.chmod(0o600)
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return data.get("token")
    except (OSError, json.JSONDecodeError):
        return None


def clear_token() -> None:
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
