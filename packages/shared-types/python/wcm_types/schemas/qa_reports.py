"""Schemas pydantic para qa_reports (v0.16.0)."""

from __future__ import annotations

from typing import Any

from wcm_types.schemas._base import TimestampedRead


class QaReportRead(TimestampedRead):
    """Lectura de la última fila `qa_reports` de un proyecto.

    Scores Lighthouse normalizados 0-100. NULL = no medido (Lighthouse
    no estaba disponible). Counts de errores HTML / broken links son
    siempre enteros (>=0). Booleanos del bloque "checks binarios"
    pueden ser None si la comprobación se skippeó.

    `report_json` lleva detalle drill-down (Lighthouse JSON completo,
    lista de errores HTML, lista de links rotos) sin necesidad de
    re-ejecutar el agent.
    """

    id: int
    project_id: int

    # Lighthouse (0-100 o None).
    lighthouse_perf_desktop: int | None = None
    lighthouse_perf_mobile: int | None = None
    lighthouse_a11y_avg: int | None = None
    lighthouse_best_practices_avg: int | None = None
    lighthouse_seo_avg: int | None = None

    # Validación HTML W3C.
    html_validator_errors_count: int = 0
    html_validator_warnings_count: int = 0

    # Link checker.
    broken_links_count: int = 0
    total_links_checked: int = 0

    # Checks binarios.
    https_valid: bool | None = None
    robots_accessible: bool | None = None
    sitemap_accessible: bool | None = None

    report_json: dict[str, Any] | None = None
