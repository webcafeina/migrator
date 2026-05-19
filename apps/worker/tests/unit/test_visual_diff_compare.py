"""Tests del helper visual_diff_compare (v0.16.0)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from wcm_worker.integrations.visual_diff_compare import compare


def _png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_imagenes_identicas_score_1() -> None:
    png = _png(50, 50, (255, 255, 255))
    result = compare(png, png)
    assert result.score == 1.0
    assert result.mismatched_pixels == 0
    assert result.total_pixels == 50 * 50


def test_imagenes_totalmente_distintas_score_bajo() -> None:
    white = _png(50, 50, (255, 255, 255))
    black = _png(50, 50, (0, 0, 0))
    result = compare(white, black)
    assert result.score < 0.1
    assert result.mismatched_pixels > 2000  # >80% de los 2500 px


def test_dimensiones_distintas_recorta_al_minimo() -> None:
    big = _png(100, 200, (128, 128, 128))
    small = _png(80, 100, (128, 128, 128))
    result = compare(big, small)
    # Recorta a (80, 100).
    assert result.width == 80
    assert result.height == 100
    assert result.score == 1.0  # mismo color → idénticas dentro del crop


def test_overlay_devuelve_png_valido() -> None:
    white = _png(20, 20, (255, 255, 255))
    black = _png(20, 20, (0, 0, 0))
    result = compare(white, black)
    # Overlay debe ser un PNG decodificable.
    overlay = Image.open(io.BytesIO(result.overlay_png))
    assert overlay.size == (20, 20)
    # Y debe tener pixeles rojos (diff_color).
    pixels = list(overlay.getdata())
    has_red = any(p[0] > 200 and p[1] < 50 and p[2] < 50 for p in pixels)
    assert has_red, "Overlay no contiene píxeles rojos (esperados por diff_color)"


def test_imagen_1px_vs_normal_recorta_a_1x1() -> None:
    """Edge case: imagen 1×1 vs imagen normal. min común = 1×1,
    compara solo ese único pixel."""
    one_px = _png(1, 1, (255, 255, 255))
    normal = _png(50, 50, (255, 255, 255))
    result = compare(one_px, normal)
    assert result.width == 1
    assert result.height == 1
    assert result.score == 1.0  # mismo color en el píxel común
    assert result.total_pixels == 1
