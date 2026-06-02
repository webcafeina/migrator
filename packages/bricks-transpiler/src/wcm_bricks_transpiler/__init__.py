"""Webcafeína Migrator — transpilador ContentBlock → Bricks Builder JSON.

Punto de entrada principal: `transpile_page(content_blocks, ctx) -> TranspileResult`.
"""

from wcm_bricks_transpiler.bricks_adapter import (
    AdapterStats,
    adapt_to_bricks_native,
)
from wcm_bricks_transpiler.global_classes_catalog import (
    CANONICAL_CLASS_IDS,
    CLASS_DESCRIPTIONS,
    build_canonical_catalog,
    list_canonical_ids,
)
from wcm_bricks_transpiler.ids import IdGenerator, make_element_id
from wcm_bricks_transpiler.schema import (
    BRICKS_ELEMENT_NAMES,
    BRICKS_SCHEMA_VERSION,
    BricksElement,
    BricksThemeStyles,
)
from wcm_bricks_transpiler.theme import build_theme_styles
from wcm_bricks_transpiler.transpiler import (
    TranspileContext,
    TranspileResult,
    transpile_page,
)
from wcm_bricks_transpiler.validator import (
    ValidationIssue,
    ValidationResult,
    validate_bricks_page,
)

__all__ = [
    "BRICKS_ELEMENT_NAMES",
    "BRICKS_SCHEMA_VERSION",
    "CANONICAL_CLASS_IDS",
    "CLASS_DESCRIPTIONS",
    "AdapterStats",
    "BricksElement",
    "BricksThemeStyles",
    "IdGenerator",
    "TranspileContext",
    "TranspileResult",
    "ValidationIssue",
    "ValidationResult",
    "adapt_to_bricks_native",
    "build_canonical_catalog",
    "build_theme_styles",
    "list_canonical_ids",
    "make_element_id",
    "transpile_page",
    "validate_bricks_page",
]
