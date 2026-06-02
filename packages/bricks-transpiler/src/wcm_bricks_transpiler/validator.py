"""Validador independiente del output del transpilador.

Se ejecuta como gate antes de persistir un `bricks_pages.bricks_json`. Si
hay errores `severity="error"`, el bricks-transpiler agente debe fallar
con `SchemaValidationError`.

Diseño: en lugar de un único bool, devolvemos un `ValidationResult` con
lista de issues — más útil para reportar al operador.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from wcm_bricks_transpiler.schema import (
    ATOMIC_ELEMENTS,
    BRICKS_ELEMENT_NAMES,
    TOP_LEVEL_ONLY,
)

#: v0.27.0 — regex permisivo para IDs Bricks. Permite IDs semánticos
#: (`usp01_text`, `sec001`, `feature-icon-1`) además de los hash
#: `[a-z0-9]{6}` que genera el transpiler nativo. Bricks acepta hasta
#: 64 chars con `[a-z0-9_-]`.
_BRICKS_ID_LOOSE_RE = re.compile(r"^[a-z0-9_-]{3,64}$")

#: v0.28.0 — keys de `_typography` aceptadas por Bricks 2.1.4. Solo
#: kebab-case. snake_case (`font_size`) y camelCase (`fontSize`) son
#: ignoradas silenciosamente por Bricks → renderiza con CSS default.
#: Bug raíz del E2E v0.27.0 (mariya.design).
_TYPOGRAPHY_VALID_KEYS = frozenset({
    "font-family", "font-size", "font-weight", "line-height",
    "letter-spacing", "text-align", "text-transform", "text-decoration",
    "color", "font-style",
})

#: Keys de spacing que aceptan shape `{top, right, bottom, left}`.
_SPACING_KEYS = frozenset({"_padding", "_margin"})

#: Subkeys aceptadas en una spacing key.
_SPACING_VALID_SUBKEYS = frozenset({"top", "right", "bottom", "left"})

#: Keys de Bricks que contienen un objeto color como valor directo o
#: anidado (validar shape `{hex}` o `{raw}`).
_DIRECT_COLOR_PARENT_KEYS = frozenset({"_textColor", "_color"})

Severity = Literal["error", "warning"]


@dataclass
class ValidationIssue:
    severity: Severity
    code: str  # identificador estable para test/CI
    message: str
    element_id: str | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def validate_bricks_page(content: list[dict[str, Any]]) -> ValidationResult:
    """Valida un array de elementos Bricks (output del transpilador).

    Reglas verificadas:
    - Cada elemento tiene id, name, parent, children, settings.
    - IDs únicos en la página.
    - Cada `parent` apunta a un id existente o a "0".
    - Si parent != "0", el id correspondiente debe listarnos en sus `children`.
    - Si el name es atómico, `children` debe estar vacío.
    - Si el name es top-level-only (section), parent debe ser "0".
    - name dentro del catálogo MVP.
    """
    result = ValidationResult()

    if not isinstance(content, list):
        result.issues.append(
            ValidationIssue("error", "content_not_list", "El contenido no es una lista.")
        )
        return result

    ids_seen: set[str] = set()
    id_to_element: dict[str, dict[str, Any]] = {}

    for idx, el in enumerate(content):
        if not isinstance(el, dict):
            result.issues.append(
                ValidationIssue("error", "element_not_dict", f"Elemento {idx} no es dict.")
            )
            continue

        # Required keys
        for key in ("id", "name", "parent", "children", "settings"):
            if key not in el:
                result.issues.append(
                    ValidationIssue(
                        "error", "missing_key",
                        f"Elemento {idx} sin key '{key}'.",
                        element_id=el.get("id"),
                    )
                )

        eid = el.get("id")
        # v0.27.0 — Bricks acepta IDs de cualquier longitud `[a-z0-9_-]+`.
        # Antes exigíamos exactamente 6 chars (convención del transpiler
        # nativo), pero AIs como gpt-5-mini generan IDs semánticos como
        # `usp01_text` que son válidos en Bricks. Relajado a min 3, max
        # 64 chars, alfanumérico + guiones bajos/medios.
        if not isinstance(eid, str) or not _BRICKS_ID_LOOSE_RE.match(eid):
            result.issues.append(
                ValidationIssue(
                    "error", "invalid_id_format",
                    f"id inválido en pos {idx}: {eid!r}. Esperado [a-z0-9_-]{{3,64}}.",
                    element_id=eid if isinstance(eid, str) else None,
                )
            )
            continue

        if eid in ids_seen:
            result.issues.append(
                ValidationIssue(
                    "error", "duplicate_id",
                    f"id duplicado en página: {eid}",
                    element_id=eid,
                )
            )
        ids_seen.add(eid)
        id_to_element[eid] = el

        name = el.get("name")
        if name not in BRICKS_ELEMENT_NAMES:
            result.issues.append(
                ValidationIssue(
                    "error", "unsupported_element_name",
                    f"name '{name}' no está en el catálogo MVP.",
                    element_id=eid,
                )
            )

        parent = el.get("parent")
        if not isinstance(parent, str):
            result.issues.append(
                ValidationIssue(
                    "error", "parent_not_string",
                    f"parent de {eid} no es string (es {type(parent).__name__}).",
                    element_id=eid,
                )
            )

        children = el.get("children", [])
        if not isinstance(children, list) or not all(isinstance(c, str) for c in children):
            result.issues.append(
                ValidationIssue(
                    "error", "children_invalid",
                    f"children de {eid} debe ser lista de strings.",
                    element_id=eid,
                )
            )
            continue

        if name in ATOMIC_ELEMENTS and children:
            result.issues.append(
                ValidationIssue(
                    "error", "atomic_with_children",
                    f"Elemento atómico {name} ({eid}) tiene children: {children}.",
                    element_id=eid,
                )
            )

    # Segunda pasada: validar parents/children cruzados (requiere ids_seen completo).
    for eid, el in id_to_element.items():
        name = el.get("name")
        parent = el.get("parent")

        if name in TOP_LEVEL_ONLY and parent != "0":
            # v0.27.0 — degradado de error a warning. Bricks técnicamente
            # acepta nested sections (poco común pero válido). Modelos
            # IA como gpt-5-mini a veces crean arquitecturas con sections
            # anidadas dentro de un container raíz. No bloquear.
            result.issues.append(
                ValidationIssue(
                    "warning", "nested_section",
                    f"{name} ({eid}) anidada bajo parent={parent!r} "
                    "(práctica poco común pero válida en Bricks).",
                    element_id=eid,
                )
            )

        if parent != "0" and parent not in id_to_element:
            result.issues.append(
                ValidationIssue(
                    "error", "orphan_parent",
                    f"{eid} apunta a parent={parent!r} que no existe.",
                    element_id=eid,
                )
            )
        elif parent != "0":
            parent_el = id_to_element[parent]
            if eid not in parent_el.get("children", []):
                result.issues.append(
                    ValidationIssue(
                        "error", "parent_child_inconsistent",
                        f"{eid}.parent={parent} pero {parent}.children no contiene {eid}.",
                        element_id=eid,
                    )
                )

        for child_id in el.get("children", []):
            if child_id not in id_to_element:
                result.issues.append(
                    ValidationIssue(
                        "error", "missing_child",
                        f"{eid}.children incluye {child_id} que no existe.",
                        element_id=eid,
                    )
                )
                continue
            child_el = id_to_element[child_id]
            if child_el.get("parent") != eid:
                result.issues.append(
                    ValidationIssue(
                        "error", "child_parent_inconsistent",
                        f"{eid}.children incluye {child_id} pero {child_id}.parent={child_el.get('parent')!r}.",
                        element_id=eid,
                    )
                )

    # v0.28.0 — Tercera pasada: validar shape de settings contra el
    # corpus h2b (bricks_shape_v214.json). Detecta los 6 anti-patrones
    # críticos que causaban render sin estilos en el frontend WP.
    for eid, el in id_to_element.items():
        settings = el.get("settings") or {}
        if not isinstance(settings, dict):
            continue  # validado por children_invalid / parent_not_string en pasos previos
        _validate_settings_shape(eid, el.get("name") or "?", settings, result)

    return result


def _validate_settings_shape(
    eid: str,
    name: str,
    settings: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Valida shape de settings contra Bricks 2.1.4 verbatim.

    Detecta los anti-patrones que causaban render fallido del E2E
    v0.27.0 (proyecto Mariya Design):
    - `_typography.font_size` (underscore) o `_typography.fontSize` (camel)
      → Bricks 2.1.4 espera kebab-case `font-size`. Sin esto, ignora la
      key silenciosamente y renderiza con CSS default WP.
    - `_padding: "4rem"` (string shorthand) en lugar del objeto
      `{top, right, bottom, left}`.
    - `color: "#000"` (string plana) en lugar de `{hex: ...}` / `{raw: ...}`.
    - `image: "https://..."` (string) en lugar de `{url, id?, external?}`.
    - `_cssGlobalClasses: [{id, name}]` (objetos) en lugar de strings.
    """
    # 1. Typography keys: snake_case y camelCase prohibidos.
    typo = settings.get("_typography")
    if isinstance(typo, dict):
        for tk, tv in typo.items():
            if tk == "color":
                _check_color_shape(eid, "_typography.color", tv, result)
                continue
            if tk in _TYPOGRAPHY_VALID_KEYS:
                continue
            # Detectar snake_case (font_size) vs kebab (font-size)
            candidate_kebab = tk.replace("_", "-")
            if candidate_kebab in _TYPOGRAPHY_VALID_KEYS:
                result.issues.append(
                    ValidationIssue(
                        "error", "typography_underscore_key",
                        f"_typography.{tk!r} debe ser {candidate_kebab!r} "
                        "(Bricks ignora keys con underscore).",
                        element_id=eid,
                    )
                )
                continue
            # camelCase (fontSize → font-size)
            candidate_from_camel = re.sub(r"(?<!^)(?=[A-Z])", "-", tk).lower()
            if candidate_from_camel in _TYPOGRAPHY_VALID_KEYS:
                result.issues.append(
                    ValidationIssue(
                        "error", "typography_camelcase_key",
                        f"_typography.{tk!r} debe ser {candidate_from_camel!r} "
                        "(Bricks ignora camelCase).",
                        element_id=eid,
                    )
                )
                continue
            result.issues.append(
                ValidationIssue(
                    "warning", "typography_unknown_key",
                    f"_typography.{tk!r} no está en el catálogo Bricks 2.1.4.",
                    element_id=eid,
                )
            )

    # 2. Spacing keys (_padding, _margin) deben ser dict con top/right/bottom/left.
    for sp_key in _SPACING_KEYS:
        sp_val = settings.get(sp_key)
        if sp_val is None:
            continue
        if isinstance(sp_val, str):
            result.issues.append(
                ValidationIssue(
                    "error", "spacing_shorthand_string",
                    f"{sp_key} de {name}({eid}) es string {sp_val!r}; "
                    "Bricks espera objeto {top, right, bottom, left}.",
                    element_id=eid,
                )
            )
            continue
        if not isinstance(sp_val, dict):
            result.issues.append(
                ValidationIssue(
                    "error", "spacing_invalid_type",
                    f"{sp_key} de {name}({eid}) debe ser dict, es {type(sp_val).__name__}.",
                    element_id=eid,
                )
            )
            continue
        # subkeys inválidas
        for subk in sp_val:
            if subk not in _SPACING_VALID_SUBKEYS:
                result.issues.append(
                    ValidationIssue(
                        "warning", "spacing_unknown_subkey",
                        f"{sp_key}.{subk} no es estándar (válidos: top/right/bottom/left).",
                        element_id=eid,
                    )
                )

    # 3. _background: image debe ser dict, color debe ser dict.
    bg = settings.get("_background")
    if isinstance(bg, dict):
        if "color" in bg:
            _check_color_shape(eid, "_background.color", bg["color"], result)
        if "image" in bg:
            img = bg["image"]
            if isinstance(img, str):
                result.issues.append(
                    ValidationIssue(
                        "error", "background_image_string",
                        f"_background.image de {name}({eid}) es string; "
                        "Bricks espera {url, size, position}.",
                        element_id=eid,
                    )
                )
            elif isinstance(img, dict):
                if "url" not in img:
                    result.issues.append(
                        ValidationIssue(
                            "error", "background_image_missing_url",
                            f"_background.image de {name}({eid}) sin key 'url'.",
                            element_id=eid,
                        )
                    )

    # 4. Direct color keys.
    for ckey in _DIRECT_COLOR_PARENT_KEYS:
        if ckey in settings:
            _check_color_shape(eid, ckey, settings[ckey], result)

    # 5. Image element (image element top-level): debe ser dict con url.
    if name == "image":
        img = settings.get("image")
        if isinstance(img, str):
            result.issues.append(
                ValidationIssue(
                    "error", "image_element_string",
                    f"image de elemento image({eid}) es string; "
                    "Bricks espera {url, id?, external?, filename?}.",
                    element_id=eid,
                )
            )
        elif isinstance(img, dict):
            if "url" not in img:
                result.issues.append(
                    ValidationIssue(
                        "error", "image_element_missing_url",
                        f"image de elemento image({eid}) sin key 'url'.",
                        element_id=eid,
                    )
                )
            elif img.get("external") is not True and "id" not in img:
                # WP media library → exige id WP. external=true → solo url+filename.
                result.issues.append(
                    ValidationIssue(
                        "warning", "image_element_missing_wp_id",
                        f"image de {name}({eid}) sin 'id' WP y sin external=true. "
                        "Bricks no podrá generar srcset responsive.",
                        element_id=eid,
                    )
                )

    # 6. _cssGlobalClasses: array de strings, NO objetos.
    gc = settings.get("_cssGlobalClasses")
    if gc is not None:
        if not isinstance(gc, list):
            result.issues.append(
                ValidationIssue(
                    "error", "global_classes_not_list",
                    f"_cssGlobalClasses de {name}({eid}) debe ser lista.",
                    element_id=eid,
                )
            )
        else:
            for i, item in enumerate(gc):
                if not isinstance(item, str):
                    result.issues.append(
                        ValidationIssue(
                            "error", "global_classes_object_item",
                            f"_cssGlobalClasses[{i}] de {name}({eid}) es "
                            f"{type(item).__name__}; Bricks espera string ID.",
                            element_id=eid,
                        )
                    )


def _check_color_shape(
    eid: str,
    path: str,
    val: Any,
    result: ValidationResult,
) -> None:
    """Valida que un color sea `{hex: '#...'}` o `{raw: 'var(...)'}`."""
    if isinstance(val, str):
        result.issues.append(
            ValidationIssue(
                "error", "color_string_not_object",
                f"{path} de {eid} es string {val!r}; "
                "Bricks espera {hex: '#...'} o {raw: 'var(...)'}.",
                element_id=eid,
            )
        )
        return
    if not isinstance(val, dict):
        result.issues.append(
            ValidationIssue(
                "error", "color_invalid_type",
                f"{path} de {eid} debe ser dict, es {type(val).__name__}.",
                element_id=eid,
            )
        )
        return
    if "hex" not in val and "raw" not in val:
        result.issues.append(
            ValidationIssue(
                "error", "color_missing_hex_or_raw",
                f"{path} de {eid} sin 'hex' ni 'raw'.",
                element_id=eid,
            )
        )
