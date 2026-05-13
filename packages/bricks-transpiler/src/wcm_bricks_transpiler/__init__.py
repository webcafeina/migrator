"""Webcafeína Migrator — transpilador ContentBlock → Bricks Builder JSON.

Punto de entrada principal: `transpile_page(content_blocks, ctx) -> TranspileResult`.
"""

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
    "BricksElement",
    "BricksThemeStyles",
    "IdGenerator",
    "TranspileContext",
    "TranspileResult",
    "ValidationIssue",
    "ValidationResult",
    "build_theme_styles",
    "make_element_id",
    "transpile_page",
    "validate_bricks_page",
]
