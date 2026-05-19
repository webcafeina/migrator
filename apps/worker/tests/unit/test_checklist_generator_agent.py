"""Tests del ChecklistGeneratorAgent (v0.16.0)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wcm_types.enums import (
    ProjectStatus,
    ResidualCategory,
    ResidualStatus,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.checklist_generator import (
    ChecklistGeneratorAgent,
    _format_hours,
)
from wcm_worker.errors import ChecklistGeneratorError


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.client_name = "Bar Pepe S.L."
    p.source_url = "https://barpepe.es"
    p.target_domain = "barpepe-nueva.webcafeina.com"
    p.status = ProjectStatus.COMPLETED
    p.checklist_md_url = None
    p.checklist_pdf_url = None
    return p


def _residual(
    *,
    rid: int = 1,
    title: str = "Configurar pasarela de pago",
    category: ResidualCategory = ResidualCategory.BLOCKING_GO_LIVE,
    status: ResidualStatus = ResidualStatus.OPEN,
    estimated_minutes: int | None = 30,
) -> MagicMock:
    r = MagicMock()
    r.id = rid
    r.project_id = 7
    r.title = title
    r.description = f"Descripción de la tarea #{rid}."
    r.category = category
    r.status = status
    r.estimated_minutes = estimated_minutes
    r.generated_by = "qa-runner"
    r.assignee_hint = None
    r.clickup_task_id = None
    return r


def test_helper_format_hours() -> None:
    assert _format_hours(30) == "30 min"
    assert _format_hours(60) == "1 h"
    assert _format_hours(90) == "1 h 30 min"
    assert _format_hours(120) == "2 h"
    assert _format_hours(0) == "0 min"


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(ChecklistGeneratorError, match="project_id"):
        ChecklistGeneratorAgent().run(AgentContext(session=fake_session))


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(ChecklistGeneratorError, match="no encontrado"):
        ChecklistGeneratorAgent().run(AgentContext(session=fake_session, project_id=99))


def test_agent_sin_residuales_genera_checklist_minimo(fake_session) -> None:
    project = _project_mock()
    fake_session.get.return_value = project
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = res

    result = ChecklistGeneratorAgent(r2=None).run(AgentContext(session=fake_session, project_id=7))

    assert result.outputs["residual_tasks_count"] == 0
    assert project.checklist_md_url is not None  # file:// fallback
    # PDF puede generarse o no según WeasyPrint disponible.


def test_agent_con_residuales_agrupa_por_categoria(fake_session) -> None:
    project = _project_mock()
    fake_session.get.return_value = project
    residuals = [
        _residual(rid=1, category=ResidualCategory.BLOCKING_GO_LIVE),
        _residual(
            rid=2,
            title="Revisar copy homepage",
            category=ResidualCategory.VISUAL_CONTENT,
        ),
        _residual(
            rid=3,
            title="Optimizar imágenes hero",
            category=ResidualCategory.POST_GO_LIVE,
            status=ResidualStatus.DONE,
        ),
    ]
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: residuals))
    fake_session.execute.return_value = res

    result = ChecklistGeneratorAgent(r2=None).run(AgentContext(session=fake_session, project_id=7))

    assert result.outputs["residual_tasks_count"] == 3
    # MD se generó y se persistió la URL.
    assert project.checklist_md_url is not None
    assert "checklist" in project.checklist_md_url.lower()


def test_agent_renderiza_metadata_correcta(fake_session) -> None:
    """Verifica que el MD tiene los campos del proyecto + contadores."""
    project = _project_mock()
    fake_session.get.return_value = project
    residuals = [
        _residual(rid=1, status=ResidualStatus.OPEN, estimated_minutes=30),
        _residual(rid=2, status=ResidualStatus.OPEN, estimated_minutes=60),
        _residual(rid=3, status=ResidualStatus.DONE, estimated_minutes=15),
    ]
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: residuals))
    fake_session.execute.return_value = res

    # Renderizar el MD directamente (sin pasar por subida).
    agent = ChecklistGeneratorAgent(r2=None)
    md = agent._render_markdown(project, residuals)

    assert "Bar Pepe S.L." in md
    assert "Proyecto #7" in md
    assert "barpepe.es" in md
    # Total pending = 2 open + 0 in_progress + 0 blocked.
    assert "| Abiertas | 2 |" in md
    # Estimación: 30 + 60 = 90 min pendientes (DONE no cuenta).
    assert "90 min" in md or "1 h 30 min" in md


def test_agent_weasyprint_no_disponible_genera_warning(fake_session) -> None:
    project = _project_mock()
    fake_session.get.return_value = project
    res = MagicMock()
    res.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = res

    with (
        patch(
            "wcm_worker.agents.checklist_generator.render_pdf",
            return_value=b"",
        ),
        patch(
            "wcm_worker.agents.checklist_generator.weasyprint_available",
            return_value=False,
        ),
    ):
        result = ChecklistGeneratorAgent(r2=None).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert any("WeasyPrint" in w for w in result.warnings)
    assert result.outputs["pdf_generated"] is False
