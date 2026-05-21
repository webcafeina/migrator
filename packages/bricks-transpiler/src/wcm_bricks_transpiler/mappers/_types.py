"""Tipos comunes a todos los mappers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wcm_bricks_transpiler.ids import IdGenerator
from wcm_bricks_transpiler.schema import BricksElement
from wcm_types.enums import BlockType


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
    #: C.4 (2026-05-21) — Theme styles sintetizados por `ThemeStylesAgent`.
    #: Cuando es None, los mappers usan defaults Bricks. Shape:
    #: `{"colors": {"primary","bg","text","accent"}, "typography":
    #: {"h1","h2","body","button"}, "spacing": {"section_y","container_y"}}`.
    theme_styles: dict[str, Any] | None = None
    #: v0.23.0 — Lista global de globalClasses emitidas durante esta
    #: página. Cada entrada `{id, name, settings}` se persiste en el
    #: page content para que Bricks las exponga como clases editables
    #: desde el panel. `_get_or_create_global_class` dedupea por settings
    #: hash. Mutable; los mappers la van rellenando.
    global_classes: list[dict[str, Any]] = field(default_factory=list)


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
