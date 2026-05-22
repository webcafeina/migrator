"""Heurística de calidad de imagen para detección automática de "feas".

Sprint v0.27.0 B1. Devuelve un score 0.00-1.00 + lista de flags
accionables. El dashboard muestra un badge "calidad baja" si
`score < THRESHOLD_LOW_QUALITY` (default 0.50). El operador decide si
regenera con gpt-image-2 desde `/preview`.

Heurística determinista (sin AI, sin I/O extra) — se calcula durante
`AssetOptimizerAgent` que ya tiene Pillow abierto. Penalizaciones
acumulativas según flags detectados:

| flag                       | condición                                | penalty |
|----------------------------|------------------------------------------|---------|
| low_resolution             | `max(w, h) < 800`                        | 0.30    |
| tiny_resolution            | `max(w, h) < 400`                        | +0.30   |
| obsolete_format            | mime ∈ {gif, bmp, tiff}                  | 0.20    |
| weird_aspect_ratio         | `min/max < 0.15`                         | 0.25    |
| tiny_filesize_for_size     | bytes / (w*h) < 0.05 (jpg/png con noise) | 0.15    |

`score = max(0.0, 1.0 - sum(penalties))`. Threshold "fea" = 0.50.

Caso degenerado: sin width/height → devuelve `(None, [])` (no se puede
juzgar; el dashboard simplemente no muestra badge).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: Umbral por debajo del cual una imagen se marca como "fea" en /preview.
THRESHOLD_LOW_QUALITY = Decimal("0.50")

#: Mimes que consideramos obsoletos para web moderna.
_OBSOLETE_MIMES = frozenset({"image/gif", "image/bmp", "image/tiff"})

#: Mimes "rasterizados" donde tiny_filesize_for_size aplica.
_RASTER_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class QualityAssessment:
    """Resultado del scoring. `score` None = no analizable."""

    score: Decimal | None
    flags: list[str]


def assess_image_quality(
    *,
    width: int | None,
    height: int | None,
    mime: str | None,
    size_bytes: int | None,
) -> QualityAssessment:
    """Calcula score + flags desde metadata básica del asset.

    Args:
        width: ancho en píxeles. None → no analizable.
        height: alto en píxeles. None → no analizable.
        mime: MIME type detectado (`image/jpeg`, etc.).
        size_bytes: tamaño del binario optimizado.
    """
    if not width or not height:
        return QualityAssessment(score=None, flags=[])

    flags: list[str] = []
    penalty = Decimal("0")

    max_side = max(width, height)
    min_side = min(width, height)

    # Resolution penalties (acumulativas).
    if max_side < 800:
        flags.append("low_resolution")
        penalty += Decimal("0.30")
        if max_side < 400:
            flags.append("tiny_resolution")
            penalty += Decimal("0.30")

    # Formato obsoleto.
    if mime in _OBSOLETE_MIMES:
        flags.append("obsolete_format")
        penalty += Decimal("0.20")

    # Aspect ratio: solo si claramente apaisado/vertical extremo.
    # Un logo cuadrado 200x200 NO debería caer aquí; un banner 1500x100 sí.
    ratio = Decimal(min_side) / Decimal(max_side)
    if ratio < Decimal("0.15"):
        flags.append("weird_aspect_ratio")
        penalty += Decimal("0.25")

    # Tiny filesize → posible artefacto JPG por sobre-compresión.
    # Solo aplica a rasters con dimensiones suficientes (>=400px).
    if (
        mime in _RASTER_MIMES
        and size_bytes is not None
        and size_bytes > 0
        and max_side >= 400
    ):
        bytes_per_pixel = Decimal(size_bytes) / Decimal(width * height)
        if bytes_per_pixel < Decimal("0.05"):
            flags.append("tiny_filesize_for_size")
            penalty += Decimal("0.15")

    score = max(Decimal("0.00"), Decimal("1.00") - penalty)
    # Truncar a 2 decimales para encajar en Numeric(3, 2).
    score = score.quantize(Decimal("0.01"))
    return QualityAssessment(score=score, flags=flags)


def is_low_quality(score: Decimal | None) -> bool:
    """True si `score < THRESHOLD_LOW_QUALITY` (badge "fea")."""
    if score is None:
        return False
    return score < THRESHOLD_LOW_QUALITY
