"""BricksAdapter: convierte JSON semántico del LLM → JSON nativo Bricks 2.1.4.

Determinista, sin LLM. Fix automático de los 6 anti-patrones que causaban
el render fallido del E2E v0.27.0 (mariya.design):

1. `_typography.font_size` → `_typography.font-size` (snake → kebab).
2. `_typography.fontSize` → `_typography.font-size` (camel → kebab).
3. `_padding: "4rem"` (string) → `{top, right, bottom, left}` (objeto).
4. `color: "#000"` (string) → `{hex: "#000"}` o `{raw: "..."}` (objeto).
5. `image: "https://..."` (string) → `{url, id?, external?, filename?}` (objeto).
6. `_cssGlobalClasses: [{id, name}]` → `[id]` (lista de strings).

Adicional: inyecta `wp_media_id` cuando el `image.url` está en el `wp_asset_map`
(ya subido a WP). Necesario para que Bricks pueda generar srcset responsive
y use el media library en lugar de URLs externas.

Idempotente: input ya adaptado se devuelve sin cambios. Tests aseguran que
output siempre pasa el validator B1.
"""

from __future__ import annotations

import copy
import re
from typing import Any

__all__ = ["adapt_to_bricks_native", "AdapterStats"]

#: Keys válidas en `_typography` según corpus h2b (Bricks 2.1.4).
_TYPOGRAPHY_VALID_KEYS = frozenset({
    "font-family", "font-size", "font-weight", "line-height",
    "letter-spacing", "text-align", "text-transform", "text-decoration",
    "color", "font-style",
})

_SPACING_SUBKEYS = ("top", "right", "bottom", "left")
_SPACING_KEYS = frozenset({"_padding", "_margin"})

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_CSS_VAR_RE = re.compile(r"^var\(--[a-zA-Z0-9_-]+\)$")


class AdapterStats:
    """Contador de fixes aplicados — útil para logging/telemetría."""

    __slots__ = (
        "typography_keys_fixed",
        "spacing_expanded",
        "color_wrapped",
        "image_element_wrapped",
        "background_image_wrapped",
        "global_classes_flattened",
        "global_classes_dropped_unknown",
        "image_wp_id_injected",
    )

    def __init__(self) -> None:
        self.typography_keys_fixed = 0
        self.spacing_expanded = 0
        self.color_wrapped = 0
        self.image_element_wrapped = 0
        self.background_image_wrapped = 0
        self.global_classes_flattened = 0
        self.global_classes_dropped_unknown = 0
        self.image_wp_id_injected = 0

    def total(self) -> int:
        return sum(getattr(self, s) for s in self.__slots__)

    def as_dict(self) -> dict[str, int]:
        return {s: getattr(self, s) for s in self.__slots__}


def adapt_to_bricks_native(
    elements: list[dict[str, Any]],
    *,
    wp_asset_map: dict[str, dict[str, Any]] | None = None,
    valid_class_ids: set[str] | None = None,
    stats: AdapterStats | None = None,
) -> list[dict[str, Any]]:
    """Devuelve una copia profunda de `elements` con shape Bricks 2.1.4 verbatim.

    `wp_asset_map`: dict source_url → {id, full, url, filename, ...} con los
    datos del asset ya subido a WP (asset_uploader). Cuando un `image.url`
    coincide, se inyecta `image.id`, `image.full`, etc. para que Bricks lo
    consuma desde la media library.

    `valid_class_ids`: set de IDs de Global Classes válidas (típicamente el
    catálogo canónico `CANONICAL_CLASS_IDS`). Si proporcionado, cualquier
    `_cssGlobalClasses` referenciando un ID fuera del set se dropea
    silenciosamente (incrementa `stats.global_classes_dropped_unknown`).
    Si None, no se filtra (comportamiento legacy).

    `stats`: contador opcional para telemetría. Si None, no se registra.
    """
    wp_asset_map = wp_asset_map or {}
    stats = stats if stats is not None else AdapterStats()

    out: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            out.append(el)
            continue
        adapted = copy.deepcopy(el)
        settings = adapted.get("settings")
        if isinstance(settings, dict):
            _adapt_settings(
                adapted.get("name") or "",
                settings, wp_asset_map, valid_class_ids, stats,
            )
        out.append(adapted)
    return out


# ---------- helpers privados ----------

def _adapt_settings(
    element_name: str,
    settings: dict[str, Any],
    wp_asset_map: dict[str, dict[str, Any]],
    valid_class_ids: set[str] | None,
    stats: AdapterStats,
) -> None:
    """Muta `settings` in-place aplicando las 7 transformaciones."""
    # 1. _typography keys → kebab-case
    typo = settings.get("_typography")
    if isinstance(typo, dict):
        settings["_typography"] = _normalize_typography(typo, stats)

    # 2. _padding / _margin: string shorthand → objeto
    for sp_key in _SPACING_KEYS:
        sp_val = settings.get(sp_key)
        if isinstance(sp_val, str):
            settings[sp_key] = _expand_spacing_shorthand(sp_val)
            stats.spacing_expanded += 1

    # 3. _background: color string + image string
    bg = settings.get("_background")
    if isinstance(bg, dict):
        if "color" in bg:
            new_c = _wrap_color(bg["color"])
            if new_c is not bg["color"]:
                bg["color"] = new_c
                stats.color_wrapped += 1
        if "image" in bg:
            img = bg["image"]
            if isinstance(img, str):
                bg["image"] = {
                    "url": img,
                    "size": "cover",
                    "position": "center center",
                }
                stats.background_image_wrapped += 1
            elif isinstance(img, dict):
                _maybe_inject_wp_id(img, wp_asset_map, stats)

    # 4. Elemento image: image setting debe ser dict
    if element_name == "image":
        img = settings.get("image")
        if isinstance(img, str):
            settings["image"] = _build_image_from_url(img, wp_asset_map, stats)
            stats.image_element_wrapped += 1
        elif isinstance(img, dict):
            _maybe_inject_wp_id(img, wp_asset_map, stats)

    # 5. _cssGlobalClasses: objetos → strings + filtrar contra catálogo
    gc = settings.get("_cssGlobalClasses")
    if isinstance(gc, list):
        flat: list[str] = []
        flattened_changed = False
        for item in gc:
            if isinstance(item, str):
                flat.append(item)
            elif isinstance(item, dict):
                # Extraer id; fallback a name
                v = item.get("id") or item.get("name")
                if isinstance(v, str):
                    flat.append(v)
                    flattened_changed = True
            # cualquier otro tipo se descarta silenciosamente
        if flattened_changed:
            stats.global_classes_flattened += 1

        # Filtrar contra catálogo canónico si está activado.
        if valid_class_ids is not None:
            allowed = [c for c in flat if c in valid_class_ids]
            dropped = len(flat) - len(allowed)
            if dropped > 0:
                stats.global_classes_dropped_unknown += dropped
            flat = allowed

        if flat or flattened_changed:
            settings["_cssGlobalClasses"] = flat


def _normalize_typography(
    typo: dict[str, Any],
    stats: AdapterStats,
) -> dict[str, Any]:
    """Devuelve un nuevo dict con todas las keys en kebab-case válido."""
    new_typo: dict[str, Any] = {}
    for k, v in typo.items():
        # Color preserva shape (es dict {hex|raw})
        if k == "color":
            new_typo["color"] = _wrap_color(v)
            if new_typo["color"] is not v:
                stats.color_wrapped += 1
            continue

        if k in _TYPOGRAPHY_VALID_KEYS:
            new_typo[k] = v
            continue

        # snake_case → kebab-case
        kebab = k.replace("_", "-")
        if kebab in _TYPOGRAPHY_VALID_KEYS:
            new_typo[kebab] = v
            stats.typography_keys_fixed += 1
            continue

        # camelCase → kebab-case
        from_camel = re.sub(r"(?<!^)(?=[A-Z])", "-", k).lower()
        if from_camel in _TYPOGRAPHY_VALID_KEYS:
            new_typo[from_camel] = v
            stats.typography_keys_fixed += 1
            continue

        # Key desconocida: se preserva para no perder datos del LLM. El
        # validator B1 emitirá warning `typography_unknown_key`.
        new_typo[k] = v

    return new_typo


def _expand_spacing_shorthand(s: str) -> dict[str, str]:
    """Expande `"4rem"` (1 valor), `"4rem 1rem"` (2), `"4rem 1rem 2rem"` (3)
    o `"4rem 1rem 2rem 0"` (4) al objeto Bricks `{top, right, bottom, left}`.
    Sigue convención CSS shorthand."""
    parts = s.split()
    if len(parts) == 1:
        return dict.fromkeys(_SPACING_SUBKEYS, parts[0])
    if len(parts) == 2:
        v_y, v_x = parts
        return {"top": v_y, "right": v_x, "bottom": v_y, "left": v_x}
    if len(parts) == 3:
        t, x, b = parts
        return {"top": t, "right": x, "bottom": b, "left": x}
    # 4+ valores: t r b l
    t, r, b, l = parts[:4]
    return {"top": t, "right": r, "bottom": b, "left": l}


def _wrap_color(c: Any) -> Any:
    """Si `c` es string `#hex` o `var(--...)`, lo envuelve en objeto Bricks."""
    if isinstance(c, str):
        if _HEX_RE.match(c):
            return {"hex": c}
        if _CSS_VAR_RE.match(c):
            return {"raw": c}
        # String arbitraria: asumimos CSS literal — envolvemos como raw.
        return {"raw": c}
    return c


def _build_image_from_url(
    url: str,
    wp_asset_map: dict[str, dict[str, Any]],
    stats: AdapterStats,
) -> dict[str, Any]:
    """Construye el image-element shape desde una URL plana.

    Si la URL coincide con un asset ya subido (wp_asset_map), inyecta
    `id` + `full` + `filename` desde el mapa. Si no, `external=true`.
    """
    filename = url.rsplit("/", 1)[-1] or "image"
    if url in wp_asset_map:
        wp_data = wp_asset_map[url]
        stats.image_wp_id_injected += 1
        return {
            "id": wp_data["id"],
            "filename": wp_data.get("filename", filename),
            "size": wp_data.get("size", "large"),
            "url": wp_data.get("url", url),
            "full": wp_data.get("full", url),
        }
    return {
        "url": url,
        "external": True,
        "filename": filename,
    }


def _maybe_inject_wp_id(
    img: dict[str, Any],
    wp_asset_map: dict[str, dict[str, Any]],
    stats: AdapterStats,
) -> None:
    """Si el `image.url` corresponde a un asset WP y aún no tiene `id`,
    lo inyecta. Marca el dict como WP-backed."""
    if "id" in img and img["id"]:
        return
    url = img.get("url")
    if not isinstance(url, str) or url not in wp_asset_map:
        return
    wp_data = wp_asset_map[url]
    img["id"] = wp_data["id"]
    img.setdefault("filename", wp_data.get("filename"))
    img.setdefault("size", wp_data.get("size", "large"))
    img.setdefault("full", wp_data.get("full", url))
    img.pop("external", None)
    stats.image_wp_id_injected += 1
