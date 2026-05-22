"""Sprint v0.25.0 — Pipeline Templates: catálogo Brickstemplate.com + motor.

Subpaquete dedicado al pivote arquitectónico: generar páginas Bricks
desde un Brief canónico ensamblando templates predefinidos de
`brickstemplate.com` con `SectionPicker` (decisión de qué template usar)
y `SlotMapper` (reemplazo de placeholders por contenido del Brief).

Módulos:
- `section_picker.py`: motor de selección de templates por sección.
- `slot_mapper.py`: motor de reemplazo de placeholders + reasignación
  de IDs Bricks.

El `RedesignTemplatesAgent` en `apps/worker/.../agents/redesign_templates.py`
orquesta ambos módulos por cada `Brief.pages[i].sections[j]`.
"""

from __future__ import annotations

from wcm_bricks_transpiler.redesign.section_picker import (
    PickedSection,
    SectionPicker,
    load_sections_index,
)
from wcm_bricks_transpiler.redesign.slot_mapper import (
    SlotMapper,
    SlotMapperError,
)

__all__ = [
    "PickedSection",
    "SectionPicker",
    "SlotMapper",
    "SlotMapperError",
    "load_sections_index",
]
