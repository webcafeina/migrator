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

    return result
