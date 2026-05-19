"""Interfaz base para extractors por builder.

Un extractor procesa HTML ya renderizado (idealmente capturado por
Playwright con hidratación completa) y devuelve bloques semánticos
normalizados (`BlockType` del dominio).

Cada extractor implementa heurísticas específicas del builder origen
(selectores característicos de Wix, attrs `data-w-id` de Webflow,
`data-block-type` de Hostinger AI). Los selectores se documentan en los
SKILL.md correspondientes; aquí se codifican como atributos `_SELECTORS`
de la clase para mantenibilidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from wcm_types.enums import BlockType


@dataclass
class ExtractedBlock:
    """Bloque semántico extraído del HTML — equivalente al input de
    `content-extractor` agente, listo para alimentar a bricks-transpiler.
    """

    block_type: BlockType
    order_index: int
    content_json: dict[str, Any] = field(default_factory=dict)
    lang: str | None = None
    notes: str | None = None  # para bloques unknown o parcialmente extraídos


@dataclass
class ExtractionResult:
    blocks: list[ExtractedBlock] = field(default_factory=list)
    asset_urls: list[str] = field(default_factory=list)
    font_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    page_lang: str | None = None
    page_title: str | None = None
    detected_classes: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    #: v0.19.0 — Theme colors detectados (`{primary, secondary, accent}`).
    #: Bricks-transpiler los aplica a Theme Styles globales.
    theme_colors: dict[str, str] = field(default_factory=dict)
    #: v0.19.0 — Theme fonts detectados (`{heading, body}`).
    theme_fonts: dict[str, str] = field(default_factory=dict)
    #: v0.19.0 — Información de contacto extraída (email, phone, social).
    #: Útil para sembrar el form de contacto y residuales del checklist.
    contact_info: dict[str, str | list[str]] = field(default_factory=dict)


class BuilderExtractor(Protocol):
    """Interfaz que cumple cada extractor."""

    builder_name: str

    def hydration_wait_selector(self) -> str | None:
        """Selector que indica que la página está completamente hidratada.

        scraper-origin agente lo usa con `page.wait_for_selector` antes de
        capturar el HTML final. Devolver None si no aplica.
        """
        ...

    def hydration_extra_wait_ms(self) -> int:
        """Esperar este margen tras el selector de hidratación."""
        ...

    def extract(self, html: str, url: str) -> ExtractionResult:
        """Extrae bloques semánticos del HTML hidratado."""
        ...
