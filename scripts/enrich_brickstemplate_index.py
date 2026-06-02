"""Enriquece sections-index.json del catálogo brickstemplate.

v0.28.0 B13. Tras descargar el catálogo con
`import_brickstemplate_clipboard.py`, este script:

1. Reestructura el índice del formato lista plana al shape `{"templates": [...]}`
   que `SectionPicker` espera (`load_sections_index` línea 69).
2. Por cada template, abre el JSON original y genera `slot_map` heurístico
   (heading→headline, button→cta.text/url, image→image_url, etc.) que
   `SlotMapper` consume.
3. Aplica mapping de categorías brickstemplate → Brief (`call-to-action`
   → `cta`, `contact-us` → `contact_form`, etc.) para que SectionPicker
   filtre por `section.type` del Brief sin reescribir nada.
4. Sobrescribe `sections-index.json` con la versión enriquecida.

Idempotente: re-ejecutar es seguro. Si una entrada ya tiene `slot_map`
no vacío, se respeta (override manual gana).

Uso:
    python scripts/enrich_brickstemplate_index.py [--dry-run]

`--dry-run` (default) muestra qué cambiaría sin escribir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CATALOG_ROOT = Path("docs/templates/brickstemplate")
INDEX_PATH = CATALOG_ROOT / "sections-index.json"

#: Mapping brickstemplate.category → SectionPicker.section_type (Brief).
#: Categorías sin entrada se preservan tal cual.
CATEGORY_ALIAS_MAP: dict[str, str] = {
    "call-to-action": "cta",
    "contact-us": "contact_form",
    "post-grid": "post_grid",
    "post-loop": "post_loop",
    "post-section": "post_section",
    "product-categories": "product_categories",
    "product-tabs": "product_tabs",
    "pros-and-cons": "pros_cons",
    "single-post": "single_post",
    "single-product": "single_product",
    "table-of-contents": "toc",
    "coming-soon": "coming_soon",
    "email-opt-in": "email_opt_in",
    "error-page": "error_page",
    "back-to-top": "back_to_top",
    "bio-links": "bio_links",
}

#: Elementos atómicos donde buscar contenido del Brief.
_HEADING_NAMES = frozenset({"heading"})
_TEXT_NAMES = frozenset({"text-basic", "text", "text-link"})
_BUTTON_NAMES = frozenset({"button"})
_IMAGE_NAMES = frozenset({"image"})
_LOGO_NAMES = frozenset({"logo"})


def normalize_category(brickstemplate_category: str) -> str:
    """Aplica mapping brickstemplate → Brief naming."""
    return CATEGORY_ALIAS_MAP.get(brickstemplate_category, brickstemplate_category)


def generate_slot_map(content: list[dict[str, Any]]) -> dict[str, str]:
    """Heurística determinista para generar slot_map por template.

    Asigna slots en el orden en que aparecen los elementos atómicos:
    - 1er heading h1/h2 → headline
    - 2º heading (cualquier tag) → subheadline
    - 1er text-basic largo (>40 chars) → description
    - 1er button text → cta.text + link.url → cta.url
    - 2º button (si existe) → cta_secondary.text/url
    - 1er logo logoText → logo_text
    - 1er image → image_url + image_id
    - 1er _background.image → background_image_url

    Solo emite slots donde el path JSON existe en el template (defensivo).
    """
    slot_map: dict[str, str] = {}
    headings: list[tuple[int, dict]] = []
    texts: list[tuple[int, dict]] = []
    buttons: list[tuple[int, dict]] = []
    images: list[tuple[int, dict]] = []
    logos: list[tuple[int, dict]] = []
    bg_image_indices: list[int] = []

    for i, el in enumerate(content):
        if not isinstance(el, dict):
            continue
        name = el.get("name")
        settings = el.get("settings") or {}
        if name in _HEADING_NAMES:
            headings.append((i, el))
        elif name in _TEXT_NAMES:
            text = settings.get("text", "")
            if isinstance(text, str) and len(text.strip()) > 40:
                texts.append((i, el))
        elif name in _BUTTON_NAMES:
            buttons.append((i, el))
        elif name in _IMAGE_NAMES:
            images.append((i, el))
        elif name in _LOGO_NAMES:
            logos.append((i, el))
        bg = settings.get("_background") or {}
        if isinstance(bg, dict) and isinstance(bg.get("image"), dict):
            bg_image_indices.append(i)

    # Headings → headline + subheadline
    if headings:
        idx, _ = headings[0]
        slot_map[f"content[{idx}].settings.text"] = "headline"
    if len(headings) >= 2:
        idx, _ = headings[1]
        slot_map[f"content[{idx}].settings.text"] = "subheadline"

    # Texts → description
    if texts:
        idx, _ = texts[0]
        slot_map[f"content[{idx}].settings.text"] = "description"

    # Buttons → cta + cta_secondary
    if buttons:
        idx, el = buttons[0]
        slot_map[f"content[{idx}].settings.text"] = "cta.text"
        # Link solo si el template ya tiene link.url (no inventamos shape)
        if isinstance((el.get("settings") or {}).get("link"), dict):
            slot_map[f"content[{idx}].settings.link.url"] = "cta.url"
    if len(buttons) >= 2:
        idx, el = buttons[1]
        slot_map[f"content[{idx}].settings.text"] = "cta_secondary.text"
        if isinstance((el.get("settings") or {}).get("link"), dict):
            slot_map[f"content[{idx}].settings.link.url"] = "cta_secondary.url"

    # Logo (típico de header/footer)
    if logos:
        idx, el = logos[0]
        # logoText es el campo nativo del element logo
        if "logoText" in (el.get("settings") or {}):
            slot_map[f"content[{idx}].settings.logoText"] = "logo_text"

    # Image element (primer image)
    if images:
        idx, el = images[0]
        img = (el.get("settings") or {}).get("image") or {}
        if "url" in img:
            slot_map[f"content[{idx}].settings.image.url"] = "image_url"
        if "id" in img:
            slot_map[f"content[{idx}].settings.image.id"] = "image_id"

    # Background image (primer _background.image)
    if bg_image_indices:
        idx = bg_image_indices[0]
        slot_map[f"content[{idx}].settings._background.image.url"] = "background_image_url"

    return slot_map


def enrich_entry(entry: dict[str, Any], catalog_root: Path) -> dict[str, Any]:
    """Enriquece una entrada del índice con id, slot_map heurístico, category_brief."""
    file_path = catalog_root / entry["file"]
    if not file_path.exists():
        # Sin JSON, no podemos generar slot_map — preservar entry tal cual
        entry.setdefault("slot_map", {})
        entry.setdefault("fits_sectors", [])
        entry.setdefault("fits_tones", [])
        entry.setdefault("id", entry.get("slug", ""))
        entry.setdefault("category_original", entry.get("category", ""))
        entry["category"] = normalize_category(entry.get("category_original", ""))
        return entry

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        entry.setdefault("slot_map", {})
        entry.setdefault("fits_sectors", [])
        entry.setdefault("fits_tones", [])
        return entry

    content = payload.get("content") or []

    enriched = {
        **entry,
        "id": entry.get("slug", "") or entry.get("id", ""),
        "category_original": entry.get("category", ""),
        "category": normalize_category(entry.get("category", "")),
    }

    # Slot map: NO sobrescribir si ya existe y tiene contenido
    existing_slot_map = entry.get("slot_map") or {}
    if not existing_slot_map:
        enriched["slot_map"] = generate_slot_map(content)
    else:
        enriched["slot_map"] = existing_slot_map

    enriched.setdefault("fits_sectors", entry.get("fits_sectors") or [])
    enriched.setdefault("fits_tones", entry.get("fits_tones") or [])

    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Sobrescribe sections-index.json (default: dry-run con resumen)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run

    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} no existe", file=sys.stderr)
        return 1

    raw = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    # Compatibilidad: si ya está envuelto {"templates": [...]}, extraer.
    if isinstance(raw, dict) and "templates" in raw:
        entries = raw["templates"]
    elif isinstance(raw, list):
        entries = raw
    else:
        print(f"ERROR: shape del índice no reconocido", file=sys.stderr)
        return 1

    enriched_entries: list[dict[str, Any]] = []
    slots_total = 0
    no_slots = 0
    for entry in entries:
        enriched = enrich_entry(entry, CATALOG_ROOT)
        slot_count = len(enriched.get("slot_map") or {})
        slots_total += slot_count
        if slot_count == 0:
            no_slots += 1
        enriched_entries.append(enriched)

    # Categorías presentes tras normalización.
    from collections import Counter
    categories = Counter(e["category"] for e in enriched_entries)

    out_payload = {"templates": enriched_entries}

    print(f"=== Enrich brickstemplate index ===")
    print(f"Templates totales: {len(enriched_entries)}")
    print(f"Slots emitidos en total: {slots_total} (avg {slots_total/len(enriched_entries):.1f}/template)")
    print(f"Templates sin slot_map: {no_slots}")
    print(f"\nCategorías (tras normalización):")
    for cat, n in sorted(categories.items()):
        print(f"  {cat:<25} {n}")
    print()

    if apply:
        INDEX_PATH.write_text(
            json.dumps(out_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[APPLY] {INDEX_PATH} actualizado.")
    else:
        print(f"[DRY-RUN] Re-ejecuta con --apply para escribir.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
