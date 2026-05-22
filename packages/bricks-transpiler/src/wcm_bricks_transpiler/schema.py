"""Tipos del esquema Bricks Builder.

Esquema observacional v1 — basado en docs públicas y exports de comunidad.
La estructura final se calibrará cuando llegue el export real (WCM-001).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BRICKS_SCHEMA_VERSION = "observational-v1"

#: ID válido para `BricksElement.id` / `.parent`. 6 chars hex (dígitos +
#: letras a-f). El validador anterior usaba `.islower()` que devuelve
#: False para strings sin letras (p.ej. "815892") — rechazaba ~6% de
#: los IDs generados por `make_element_id`. Visto en proyecto 20.
_BRICKS_ID_RE = re.compile(r"^[a-z0-9]{6}$")

#: Catálogo de element names soportados en el MVP. Cualquier otro valor
#: se rechaza por el validador.
BRICKS_ELEMENT_NAMES: frozenset[str] = frozenset(
    {
        # layout
        "section", "container", "block", "div",
        # texto
        "heading", "text", "text-basic", "text-link",
        # media
        "image", "image-gallery", "video", "icon", "icon-box",
        # interactivos (v0.24.0 — slider/tabs/accordion nested)
        "button", "accordion", "accordion-nested",
        "slider-nested", "tabs-nested",
        "nav-menu", "nav-nested", "form", "shortcode",
        # utilidad
        "divider", "spacer", "code",
        # woocommerce
        "woocommerce-products", "woocommerce-product",
    }
)

#: Element names que solo pueden vivir como top-level (parent="0").
TOP_LEVEL_ONLY: frozenset[str] = frozenset({"section"})

#: Element names que NO pueden tener children (atómicos).
ATOMIC_ELEMENTS: frozenset[str] = frozenset(
    {
        "heading", "text", "text-basic",
        "image", "video", "icon",
        "button", "shortcode", "code",
        "divider", "spacer",
        "woocommerce-product",
    }
)

#: Breakpoints estándar Bricks 2.0+ (mapeo nombre → max-width px).
DEFAULT_BREAKPOINTS: dict[str, int] = {
    "desktop": 992,
    "tablet_portrait": 991,
    "mobile_landscape": 767,
    "mobile_portrait": 478,
}


ElementId = str  # Alias documental para [a-z0-9]{6}.


class BricksElement(BaseModel):
    """Un elemento dentro del array de contenido de una página Bricks."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(pattern=r"^[a-z0-9]{6}$")
    name: str
    parent: str = Field(description="ID del padre, o '0' si top-level")
    children: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None

    @field_validator("name")
    @classmethod
    def _name_in_catalog(cls, v: str) -> str:
        if v not in BRICKS_ELEMENT_NAMES:
            raise ValueError(
                f"element name '{v}' no está en el catálogo MVP. "
                f"Si es válido en Bricks, añadirlo a BRICKS_ELEMENT_NAMES."
            )
        return v

    @field_validator("parent")
    @classmethod
    def _parent_format(cls, v: str) -> str:
        # parent siempre es string. "0" o [a-z0-9]{6}. Validador con
        # regex en lugar de `.islower()` porque éste devuelve False
        # cuando el string es todo dígitos (caso real "815892" en
        # proyecto 20: hex válido que rompía el transpile).
        if v != "0" and not _BRICKS_ID_RE.match(v):
            raise ValueError(
                f"parent debe ser '0' o un ID válido [a-z0-9]{{6}}; recibido: {v!r}"
            )
        return v


class BricksColorEntry(BaseModel):
    """Una entrada de la paleta global de Bricks Builder.

    G.6 (2026-05-21) — Bricks 2.3.5 espera shape exacto `{id, name, raw}`
    y genera `--bricks-color-<id>` como CSS custom property en `:root`.
    Antes se emitía `{name, color}` que Bricks ignora silenciosamente
    al generar las variables, dejando los `var(--primary)` de los
    mappers sin resolver.
    """

    model_config = ConfigDict(extra="forbid")

    #: Slug usado en `--bricks-color-<id>` (a-z0-9-). Por convención el
    #: mismo string que `name.lower().replace(' ', '-')`.
    id: str
    #: Label legible mostrado en el editor.
    name: str
    #: Valor CSS del color (hex, rgb, rgba, var…). Bricks lo serializa
    #: como `raw` en el JSON de la option.
    raw: str


class BricksThemeStylesEntry(BaseModel):
    model_config = ConfigDict(extra="allow")  # Bricks puede añadir keys nuevas
    id: str
    label: str
    settings: dict[str, dict[str, Any]] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)


class BricksThemeStyles(BaseModel):
    """Theme Styles globales — corresponden a la option `bricks_global_settings`."""

    model_config = ConfigDict(extra="forbid")

    theme_styles: list[BricksThemeStylesEntry] = Field(default_factory=list)
    # Nombre exacto requerido por el JSON schema de Bricks Builder.
    colorPalette: list[BricksColorEntry] = Field(default_factory=list)  # noqa: N815
    breakpoints: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_BREAKPOINTS))
    #: Bug I (2026-05-21) — Bricks lee esta key para decidir qué post types
    #: muestran el botón "Edit with Bricks". Sin ella → no aparece el botón.
    #: Por defecto `page` y `post` (Bricks core). El operador puede añadir
    #: CPTs después desde wp-admin > Bricks > Settings.
    post_types: list[str] = Field(
        default_factory=lambda: ["page", "post"],
        alias="postTypes",
    )
    #: G.7 (2026-05-21) — Custom code inyectado por Bricks en `<head>`
    #: del frontend. Lo usamos para meter el `<link>` de Google Fonts:
    #: ``{"headerScripts": "<link href='https://fonts.googleapis.com/...' rel='stylesheet'>"}``
    #: Bricks lo carga en cada página independientemente del theme styles.
    custom_code: dict[str, str] = Field(
        default_factory=dict,
        alias="customCode",
    )


# Helpers de tipo para construir settings comunes.

Breakpoint = Literal["desktop", "tablet_portrait", "mobile_landscape", "mobile_portrait"]


def settings_with_breakpoint(
    base: dict[str, Any], breakpoint: Breakpoint, overrides: dict[str, Any]
) -> dict[str, Any]:
    """Inyecta un override responsive con sufijo `:breakpoint`.

    Cada key de `overrides` se serializa como `{key}:{breakpoint}` en el dict
    raíz de settings (patrón A documentado en bricks-json-schema/SKILL.md).
    """
    result = dict(base)
    for key, value in overrides.items():
        if breakpoint == "desktop":
            result[key] = value
        else:
            result[f"{key}:{breakpoint}"] = value
    return result
