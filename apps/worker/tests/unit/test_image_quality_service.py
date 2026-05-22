"""Tests del helper image_quality (Sprint v0.27.0 B1).

Heurística determinista sin AI; tests con fixtures de metadata.
"""

from __future__ import annotations

from decimal import Decimal

from wcm_worker.services.image_quality import (
    THRESHOLD_LOW_QUALITY,
    QualityAssessment,
    assess_image_quality,
    is_low_quality,
)


def test_hd_jpeg_score_perfecto() -> None:
    r = assess_image_quality(
        width=1920, height=1080, mime="image/jpeg",
        size_bytes=350_000,  # ~0.17 bytes/pixel, OK
    )
    assert r.score == Decimal("1.00")
    assert r.flags == []
    assert is_low_quality(r.score) is False


def test_low_resolution_aplica_penalty_30() -> None:
    r = assess_image_quality(
        width=640, height=480, mime="image/jpeg", size_bytes=80_000,
    )
    assert r.score == Decimal("0.70")
    assert "low_resolution" in r.flags
    assert "tiny_resolution" not in r.flags


def test_tiny_resolution_acumula_60_total() -> None:
    """max(w,h)<400 dispara low_resolution Y tiny_resolution (acumulativo)."""
    r = assess_image_quality(
        width=300, height=200, mime="image/jpeg", size_bytes=20_000,
    )
    # low (-0.30) + tiny (-0.30) = -0.60. tiny_filesize NO aplica (max<400).
    assert r.score == Decimal("0.40")
    assert "low_resolution" in r.flags
    assert "tiny_resolution" in r.flags
    assert is_low_quality(r.score) is True


def test_obsolete_format_gif() -> None:
    r = assess_image_quality(
        width=1200, height=800, mime="image/gif", size_bytes=200_000,
    )
    assert r.score == Decimal("0.80")
    assert r.flags == ["obsolete_format"]


def test_obsolete_format_bmp() -> None:
    r = assess_image_quality(
        width=1200, height=800, mime="image/bmp", size_bytes=2_000_000,
    )
    assert "obsolete_format" in r.flags


def test_weird_aspect_ratio_banner_finito() -> None:
    """1500x100 → ratio 100/1500=0.066 < 0.15."""
    r = assess_image_quality(
        width=1500, height=100, mime="image/jpeg", size_bytes=30_000,
    )
    assert "weird_aspect_ratio" in r.flags
    # weird (-0.25) + tiny_filesize (30000 / 150000 = 0.2 → NO aplica) = 0.75
    assert r.score == Decimal("0.75")


def test_aspect_ratio_logo_cuadrado_no_es_raro() -> None:
    """Logo 400x400: square, ratio 1.0 → no weird_aspect_ratio."""
    r = assess_image_quality(
        width=400, height=400, mime="image/png", size_bytes=20_000,
    )
    assert "weird_aspect_ratio" not in r.flags
    # tiny_filesize: 20000 / 160000 = 0.125 → NO aplica


def test_tiny_filesize_jpeg_sobrecomprimido() -> None:
    """1000x1000 con 3KB (3/1M = 0.003 < 0.05) → JPG sobrecomprimido."""
    r = assess_image_quality(
        width=1000, height=1000, mime="image/jpeg", size_bytes=3_000,
    )
    assert "tiny_filesize_for_size" in r.flags
    # solo tiny_filesize (-0.15)
    assert r.score == Decimal("0.85")


def test_tiny_filesize_no_aplica_a_webp_pequeno() -> None:
    """WebP comprime mucho — bytes_per_pixel bajo es normal en webp.
    El helper solo aplica a JPG/PNG donde sobre-compresión = artefactos."""
    r = assess_image_quality(
        width=1200, height=800, mime="image/webp", size_bytes=15_000,
    )
    # WebP es raster_mime → SÍ aplica (decidimos esto en el helper).
    # 15000 / 960000 = 0.0156 < 0.05 → flag.
    assert "tiny_filesize_for_size" in r.flags


def test_combinacion_low_res_obsolete_aspect() -> None:
    """Caso peor: GIF 200x20 (ratio 0.10 < 0.15)."""
    r = assess_image_quality(
        width=200, height=20, mime="image/gif", size_bytes=5_000,
    )
    # low (-0.30) + tiny (-0.30) + obsolete (-0.20) + weird (-0.25) = -1.05
    # clamp a 0.00.
    assert r.score == Decimal("0.00")
    assert {"low_resolution", "tiny_resolution", "obsolete_format",
            "weird_aspect_ratio"} <= set(r.flags)
    assert is_low_quality(r.score) is True


def test_sin_width_height_no_analizable() -> None:
    r = assess_image_quality(width=None, height=None, mime="image/png", size_bytes=1000)
    assert r.score is None
    assert r.flags == []
    assert is_low_quality(r.score) is False


def test_width_0_no_analizable() -> None:
    r = assess_image_quality(width=0, height=0, mime="image/png", size_bytes=1000)
    assert r.score is None
    assert r.flags == []


def test_is_low_quality_threshold() -> None:
    assert is_low_quality(Decimal("0.49")) is True
    assert is_low_quality(Decimal("0.50")) is False
    assert is_low_quality(Decimal("0.51")) is False
    assert is_low_quality(None) is False
    # Sanity check del threshold.
    assert THRESHOLD_LOW_QUALITY == Decimal("0.50")


def test_quality_assessment_es_dataclass_inmutable() -> None:
    qa = QualityAssessment(score=Decimal("0.75"), flags=["low_resolution"])
    assert qa.score == Decimal("0.75")
    assert qa.flags == ["low_resolution"]
