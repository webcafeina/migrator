"""Cliente unificado para WordPress destino.

Dos canales (skill `wp-rest-bulk` + `wpcli-ssh`):
- `WpRestClient` para operaciones REST puntuales y bulks pequeños/medianos.
- `WpCliSshClient` para operaciones de admin/instalación, bulk grandes y
  todo lo que el REST no exponga (search-replace, bricks import vía
  post meta, etc.).

Configuración vía `WpClientConfig` (lectura típica desde `.env`).
"""

from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.errors import (
    WpAuthError,
    WpBulkPartialError,
    WpClientError,
    WpCliExecutionError,
    WpNotFoundError,
    WpRateLimitError,
    WpRestError,
    WpSchemaError,
    WpSshAuthError,
    WpSshConnectionError,
    WpSshError,
)
from wcm_wp_client.rest import WpRestClient
from wcm_wp_client.ssh_cli import WpCliResult, WpCliSshClient

__all__ = [
    "WpAuthError",
    "WpBulkPartialError",
    "WpClientConfig",
    "WpClientError",
    "WpCliExecutionError",
    "WpCliResult",
    "WpCliSshClient",
    "WpNotFoundError",
    "WpRateLimitError",
    "WpRestClient",
    "WpRestError",
    "WpSchemaError",
    "WpSshAuthError",
    "WpSshConnectionError",
    "WpSshError",
]
