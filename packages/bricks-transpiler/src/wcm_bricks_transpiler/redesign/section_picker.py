"""SectionPicker — decide qué template usar por sección del Brief.

Sprint v0.25.0 B5. Pieza determinista del pipeline Templates:
dada una `Brief.section` (con type + content) y el contexto del
negocio (sector + tone), elige el template más adecuado del catálogo
curado en `sections-index.json`.

Algoritmo:

1. Filtra `templates` por:
   - `category == section.type` (hero, features, services, testimonials,
     gallery, pricing, cta, contact_form, footer).
   - `business.sector in template.fits_sectors` (si fits_sectors está
     definido y es lista no vacía).
   - `business.tone_of_voice in template.fits_tones` (idem).

2. Si N>=1 candidatos → elige determinista por `hash(business.name) % N`.
   Estable entre runs del mismo proyecto.

3. Si N==0 → relax filtros progresivamente:
   - Primero quitar `fits_tones`.
   - Después quitar `fits_sectors`.
   - Si aún 0 → devuelve `None` (el agente lo trata como ResidualTask
     para que el operador pickee manualmente desde dashboard).

Fixtures de catálogo en `docs/templates/brickstemplate/sections-index.json`
(producción) o `docs/templates/brickstemplate-mock/` (tests).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("wcm.bricks_transpiler.redesign.section_picker")


@dataclass(frozen=True)
class PickedSection:
    """Resultado de `SectionPicker.pick()`."""

    template_id: str
    template_file: str  # path relativo al directorio del catálogo
    template_json: dict[str, Any]  # JSON Bricks ya cargado
    slot_map: dict[str, str]  # JSONPath simplificado → key del Brief
    fallback_level: int  # 0=match perfecto, 1=sin tone, 2=sin sector, -1=no match


def load_sections_index(catalog_dir: Path) -> list[dict[str, Any]]:
    """Carga `sections-index.json` del directorio.

    Devuelve lista vacía si el catálogo no existe (caso onboarding
    incompleto — operador no ha corrido `scripts/import_brickstemplate.py`).
    """
    index_path = catalog_dir / "sections-index.json"
    if not index_path.exists():
        log.warning(
            "sections_index_missing",
            extra={"path": str(index_path)},
        )
        return []
    try:
        with index_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("templates") or []
    except (OSError, json.JSONDecodeError) as e:
        log.warning(
            "sections_index_load_failed",
            extra={"path": str(index_path), "error": str(e)[:200]},
        )
        return []


class SectionPicker:
    """Motor de selección determinista de templates por categoría."""

    def __init__(
        self,
        *,
        catalog_dir: Path,
        templates_index: list[dict[str, Any]] | None = None,
    ) -> None:
        self.catalog_dir = catalog_dir
        # Permitir inyección de índice (tests) o cargar de disco.
        self.templates_index = (
            templates_index
            if templates_index is not None
            else load_sections_index(catalog_dir)
        )

    def pick(
        self,
        *,
        section_type: str,
        business_name: str,
        business_sector: str | None = None,
        business_tone: str | None = None,
    ) -> PickedSection | None:
        """Elige el template más adecuado o None si no hay matches.

        `business_name` se usa para `hash()` determinista, garantiza
        misma elección entre re-runs del mismo proyecto.
        """
        # Filtrar por categoría primero (siempre obligatorio).
        category_candidates = [
            t for t in self.templates_index
            if t.get("category") == section_type
        ]
        if not category_candidates:
            log.info(
                "section_picker_no_category_match",
                extra={"section_type": section_type},
            )
            return None

        # Intento 1: full match (category + sector + tone).
        chosen, level = self._try_match(
            category_candidates, business_name,
            sector=business_sector, tone=business_tone, level=0,
        )
        # Intento 2: sin tone.
        if chosen is None:
            chosen, level = self._try_match(
                category_candidates, business_name,
                sector=business_sector, tone=None, level=1,
            )
        # Intento 3: sin sector ni tone (cualquiera de la categoría).
        if chosen is None:
            chosen, level = self._try_match(
                category_candidates, business_name,
                sector=None, tone=None, level=2,
            )

        if chosen is None:
            return None

        # Cargar JSON del template desde disco.
        template_path = self.catalog_dir / chosen.get("file", "")
        template_json = self._load_template_json(template_path)
        if template_json is None:
            log.warning(
                "section_picker_template_unloadable",
                extra={"id": chosen.get("id"), "path": str(template_path)},
            )
            return None

        return PickedSection(
            template_id=chosen.get("id", ""),
            template_file=chosen.get("file", ""),
            template_json=template_json,
            slot_map=chosen.get("slot_map") or {},
            fallback_level=level,
        )

    # ---------- helpers ----------

    def _try_match(
        self,
        candidates: list[dict[str, Any]],
        business_name: str,
        *,
        sector: str | None,
        tone: str | None,
        level: int,
    ) -> tuple[dict[str, Any] | None, int]:
        """Intenta encontrar matches con los filtros dados. Devuelve
        `(chosen, level)`. Si nada matchea, `(None, level)`.
        """
        filtered: list[dict[str, Any]] = []
        for t in candidates:
            if sector and t.get("fits_sectors"):
                if sector not in t["fits_sectors"]:
                    continue
            if tone and t.get("fits_tones"):
                if tone not in t["fits_tones"]:
                    continue
            filtered.append(t)
        if not filtered:
            return None, level
        idx = _stable_hash(business_name) % len(filtered)
        return filtered[idx], level

    def _load_template_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            log.warning(
                "template_load_failed",
                extra={"path": str(path), "error": str(e)[:200]},
            )
            return None


def _stable_hash(value: str) -> int:
    """Hash determinista entre runs (md5 → int). Estable entre versiones
    Python (sin PYTHONHASHSEED variability)."""
    return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)


__all__ = ["PickedSection", "SectionPicker", "load_sections_index"]
