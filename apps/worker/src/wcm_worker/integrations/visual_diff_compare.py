"""Comparación visual de 2 screenshots PNG con pixelmatch (v0.16.0).

Pixelmatch trabaja sobre arrays RGBA planos. Usamos Pillow para decodificar
los PNG, normalizar a misma dimensión (cuando origen vs destino tienen
alturas distintas — caso típico de full-page scroll), comparar y generar
un PNG overlay con las zonas divergentes en rojo.

Score: `1 - mismatched_pixels / total_pixels`. 1.0 = idénticas, 0.0 =
totalmente diferentes. Threshold de matching por pixel: 0.15 (más
permisivo que el default 0.1 para tolerar pequeños shifts de typography
sin marcar todo el bloque).

Si las imágenes tienen tamaños distintos, recortamos la mayor a la altura
de la menor (el operador rara vez compara páginas con scroll abismalmente
distinto; cuando pasa, el residual visual lo dirá).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

log = logging.getLogger("wcm.worker.integrations.visual_diff_compare")

DEFAULT_THRESHOLD = 0.15


@dataclass(frozen=True)
class VisualCompareResult:
    """Resultado de comparar 2 screenshots."""

    score: float
    """0-1, 1.0 = idénticas."""
    mismatched_pixels: int
    total_pixels: int
    overlay_png: bytes
    """PNG del diff: original con transparencia + píxeles distintos en rojo."""
    width: int
    height: int


def compare(
    source_png: bytes,
    target_png: bytes,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> VisualCompareResult:
    """Compara 2 PNG. Devuelve score + overlay para subir a R2.

    Si las imágenes no tienen la misma dimensión, ambas se recortan
    al mínimo común (width=min, height=min). Esto es suficiente para
    detectar regresiones grandes; para auditorías milimétricas habría
    que usar `viewport=device, full_page=False` (no MVP).
    """
    from PIL import Image
    from pixelmatch import pixelmatch

    src_img = Image.open(io.BytesIO(source_png)).convert("RGBA")
    tgt_img = Image.open(io.BytesIO(target_png)).convert("RGBA")

    width = min(src_img.width, tgt_img.width)
    height = min(src_img.height, tgt_img.height)

    if width <= 0 or height <= 0:
        # Caso patológico: alguna imagen vacía.
        log.warning("visual_compare_empty_image", extra={"src": src_img.size, "tgt": tgt_img.size})
        return VisualCompareResult(
            score=0.0,
            mismatched_pixels=0,
            total_pixels=0,
            overlay_png=b"",
            width=0,
            height=0,
        )

    # Crop al mínimo común antes de comparar.
    src_cropped = src_img.crop((0, 0, width, height))
    tgt_cropped = tgt_img.crop((0, 0, width, height))

    # Pixelmatch espera bytes/list RGBA plano. PIL `.tobytes()` ya lo da.
    src_data = list(src_cropped.tobytes())
    tgt_data = list(tgt_cropped.tobytes())
    output_data = [0] * len(src_data)

    mismatched = pixelmatch(
        src_data,
        tgt_data,
        width,
        height,
        output=output_data,
        threshold=threshold,
        includeAA=False,
        alpha=0.1,
        diff_color=(255, 0, 0),  # rojo Webcafeína-ish
    )

    total_pixels = width * height
    score = 1.0 - (mismatched / total_pixels) if total_pixels else 0.0
    score = max(0.0, min(1.0, score))

    # Reconstituir overlay PNG.
    overlay_img = Image.frombytes("RGBA", (width, height), bytes(output_data))
    buf = io.BytesIO()
    overlay_img.save(buf, format="PNG", optimize=True)
    overlay_png = buf.getvalue()

    return VisualCompareResult(
        score=score,
        mismatched_pixels=mismatched,
        total_pixels=total_pixels,
        overlay_png=overlay_png,
        width=width,
        height=height,
    )
