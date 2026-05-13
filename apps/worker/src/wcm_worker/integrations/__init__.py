"""Clientes de integraciones externas usados por el worker.

Convención:
- Cada cliente expone una clase principal (`ClickupClient`, `ResendClient`,
  `R2Client`) que acepta credenciales explícitas en el constructor (para
  tests) o lee env vars en `from_env()`.
- Cuando una credencial obligatoria falta, `from_env()` devuelve `None`
  para que el agente que lo use pueda devolver un summary "skipped" sin
  romper el pipeline.
- Cada cliente lanza errores tipados de su dominio
  (`ClickupApiError`, `ResendApiError`, `R2UploadError`).
"""

from wcm_worker.integrations.clickup import ClickupApiError, ClickupClient
from wcm_worker.integrations.r2 import R2Client, R2UploadError
from wcm_worker.integrations.resend import ResendApiError, ResendClient

__all__ = [
    "ClickupApiError",
    "ClickupClient",
    "R2Client",
    "R2UploadError",
    "ResendApiError",
    "ResendClient",
]
