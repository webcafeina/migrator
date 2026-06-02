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
        candidates, level = self.get_candidates(
            section_type=section_type,
            business_sector=business_sector,
            business_tone=business_tone,
        )
        if not candidates:
            return None
        idx = _stable_hash(business_name) % len(candidates)
        chosen = candidates[idx]
        return self._build_picked(chosen, level)

    def get_candidates(
        self,
        *,
        section_type: str,
        business_sector: str | None = None,
        business_tone: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """v0.28.0 B14 — Devuelve `(candidates_filtered, fallback_level)`.

        Expone la fase de filtrado relaxed sin aplicar el hash final.
        Permite que `LLMSectionRanker` elija entre los candidatos vía LLM.

        Niveles:
        - 0: match perfecto (category + sector + tone)
        - 1: match sin tone
        - 2: match solo categoría
        - -1: sin matches (lista vacía)
        """
        category_candidates = [
            t for t in self.templates_index
            if t.get("category") == section_type
        ]
        if not category_candidates:
            log.info(
                "section_picker_no_category_match",
                extra={"section_type": section_type},
            )
            return [], -1

        for sector, tone, level in (
            (business_sector, business_tone, 0),
            (business_sector, None, 1),
            (None, None, 2),
        ):
            filtered = [
                t for t in category_candidates
                if (not sector or not t.get("fits_sectors") or sector in t["fits_sectors"])
                and (not tone or not t.get("fits_tones") or tone in t["fits_tones"])
            ]
            if filtered:
                return filtered, level
        return [], -1

    def load_template_by_metadata(
        self,
        template_metadata: dict[str, Any],
    ) -> PickedSection | None:
        """v0.28.0 B14 — Carga el JSON del template y devuelve PickedSection.

        Usado por agentes que orquestan la selección externa (LLM ranker)
        y luego piden cargar el JSON del template elegido.
        """
        return self._build_picked(template_metadata, fallback_level=0)

    def _build_picked(
        self,
        chosen: dict[str, Any],
        fallback_level: int,
    ) -> PickedSection | None:
        """Carga JSON del template desde disco y construye PickedSection."""
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
            fallback_level=fallback_level,
        )

    # ---------- helpers ----------

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
