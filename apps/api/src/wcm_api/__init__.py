"""Webcafeína Migrator — API FastAPI.

Importable como `wcm_api`. La app FastAPI se construye en `wcm_api.main:app`.
"""

from wcm_api.main import create_app

__all__ = ["create_app"]
