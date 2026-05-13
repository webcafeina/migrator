"""Clientes a directorios B2B (Google Places, Páginas Amarillas, etc.).

Diferenciado de `extractors/`: aquí no se hace fingerprinting del builder,
sino enumeración de empresas candidatas.
"""

from wcm_scraper_core.directories.google_places import (
    GooglePlacesClient,
    GooglePlacesError,
    GooglePlacesQuotaExceeded,
    PlaceResult,
)

__all__ = [
    "GooglePlacesClient",
    "GooglePlacesError",
    "GooglePlacesQuotaExceeded",
    "PlaceResult",
]
