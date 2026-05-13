"""Tipos comunes a todos los mappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from wcm_types.enums import BlockType

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.schema import BricksElement


@dataclass
class MapperContext:
    """Contexto compartido entre mappers de una misma página."""

    project_id: int
    page_id: int
    page_lang: str | None
    id_gen: IdGenerator
    #: Mapping asset_id (BD) → URL pública o WP attachment_id, según
    #: la estrategia de storage del proyecto. Inyectado por transpile_page.
    asset_resolver: Callable[[int], dict[str, Any]]


@dataclass
class ResidualHint:
    """Una sugerencia de tarea residual generada por un mapper.

    `transpile_page` la traduce a una entrada de `residual_tasks` real.
    """

    title: str
    description: str
    estimated_minutes: int | None = None
    screenshot_paths: list[str] = field(default_factory=list)


@dataclass
class MapperResult:
    """Output canónico de cualquier mapper.

    Un mapper puede:
    - Producir N elementos Bricks que entran en el array de la página.
    - Producir 0 elementos y registrar una `residual` cuando el bloque no
      es migrable (caso `unknown`, animaciones Webflow IX2, etc.).
    - Producir N elementos Y una residual (parcial — p. ej. galería sin
      lightbox migrable).
    """

    elements: list[BricksElement] = field(default_factory=list)
    residual: ResidualHint | None = None


#: Firma común de cualquier mapper. El bloque viene como dict (`content_json`
#: del modelo) para evitar acoplar con SQLAlchemy en este paquete.
BlockMapper = Callable[[dict[str, Any], int, BlockType, str | None, MapperContext], MapperResult]
