"""Tests ADR-044 — threshold cascada + residual VISUAL_CONTENT en VisualDiffAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

from wcm_worker.agents.visual_diff import VisualDiffAgent


def _project_mock(*, threshold: float | None = None) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.visual_diff_threshold = threshold
    return p


def test_threshold_prefiere_columna_proyecto(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_RESIDUAL_THRESHOLD", "0.85")
    assert VisualDiffAgent()._resolve_residual_threshold(
        _project_mock(threshold=0.60)
    ) == 0.60


def test_threshold_env_si_no_columna(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_RESIDUAL_THRESHOLD", "0.85")
    assert VisualDiffAgent()._resolve_residual_threshold(
        _project_mock(threshold=None)
    ) == 0.85


def test_threshold_default_070(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_DIFF_RESIDUAL_THRESHOLD", raising=False)
    assert VisualDiffAgent()._resolve_residual_threshold(
        _project_mock(threshold=None)
    ) == 0.70


def test_threshold_env_invalido_cae_a_default(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIFF_RESIDUAL_THRESHOLD", "not-a-float")
    assert VisualDiffAgent()._resolve_residual_threshold(
        _project_mock(threshold=None)
    ) == 0.70


def test_below_threshold_residual_contenido() -> None:
    from wcm_types.enums import ResidualCategory, ResidualStatus

    project = _project_mock(threshold=0.75)
    residual = VisualDiffAgent()._below_threshold_residual(
        project, "/contacto", score=0.42, threshold=0.75
    )
    assert residual.project_id == 7
    assert residual.category == ResidualCategory.VISUAL_CONTENT
    assert residual.status == ResidualStatus.OPEN
    assert "/contacto" in residual.title
    assert "0.42" in residual.title
    assert "0.75" in residual.title
    assert residual.generated_by == "visual-diff"
