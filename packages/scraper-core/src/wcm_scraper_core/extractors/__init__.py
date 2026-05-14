"""Extractors por builder. Cada uno implementa la interfaz BuilderExtractor."""

from __future__ import annotations

from wcm_scraper_core.extractors.base import (
    BuilderExtractor,
    ExtractedBlock,
    ExtractionResult,
)
from wcm_scraper_core.extractors.hostinger import HostingerExtractor
from wcm_scraper_core.extractors.webflow import WebflowExtractor
from wcm_scraper_core.extractors.wix import WixExtractor
from wcm_types.enums import BuilderType

_REGISTRY: dict[BuilderType, type[BuilderExtractor]] = {
    BuilderType.WIX: WixExtractor,
    BuilderType.HOSTINGER_AI: HostingerExtractor,
    BuilderType.WEBFLOW: WebflowExtractor,
}


def get_extractor(builder: BuilderType) -> BuilderExtractor:
    """Devuelve una instancia del extractor para el builder dado.

    Lanza KeyError si no hay extractor para ese builder (MVP solo soporta
    Wix/Hostinger/Webflow).
    """
    cls = _REGISTRY[builder]
    return cls()


__all__ = [
    "BuilderExtractor",
    "ExtractedBlock",
    "ExtractionResult",
    "HostingerExtractor",
    "WebflowExtractor",
    "WixExtractor",
    "get_extractor",
]
