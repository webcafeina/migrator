"""Schemas pydantic para visual_diffs (v0.16.0)."""

from __future__ import annotations

from pydantic import Field

from wcm_types.schemas._base import TimestampedRead, WcmModel


class VisualDiffRead(TimestampedRead):
    """Lectura de una fila `visual_diffs` desde el API.

    Una fila por página del proyecto comparada. Score 0-1 (1=idénticas).
    URLs apuntan a R2 (si configurado) o `file://...` local fallback.
    """

    id: int
    project_id: int
    page_path: str
    source_screenshot_url: str | None = None
    target_screenshot_url: str | None = None
    overlay_url: str | None = None
    score: float | None = None
    viewport_width: int = 1280


class VisualDiffsListResponse(WcmModel):
    """Respuesta del endpoint `GET /projects/{id}/visual-diffs`.

    `avg_score` es el promedio de scores no-nulos (también persistido
    en `projects.visual_diff_avg_score` para mostrar en header).
    `pages_total` indica cuántas comparaciones se hicieron.
    """

    project_id: int
    avg_score: float | None = None
    pages_total: int = Field(ge=0)
    pages: list[VisualDiffRead]
