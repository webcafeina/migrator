"""Tests del ClickupSyncerAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.clickup_syncer import ClickupSyncerAgent, _build_description
from wcm_worker.errors import ClickupSyncerError


def _residual(
    *,
    id_: int = 1,
    clickup_task_id: str | None = None,
    status: ResidualStatus = ResidualStatus.OPEN,
    category: ResidualCategory = ResidualCategory.CLIENT_CONFIG,
    assignee_hint: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = id_
    r.title = f"Tarea {id_}"
    r.description = "Lorem ipsum"
    r.category = category
    r.estimated_minutes = 30
    r.screenshot_paths = []
    r.generated_by = "qa_runner"
    r.clickup_task_id = clickup_task_id
    r.assignee_hint = assignee_hint
    r.status = status
    return r


def _ctx_with_residuals(fake_session, residuals) -> AgentContext:
    scalars = MagicMock()
    scalars.__iter__ = lambda self: iter(residuals)
    result = MagicMock()
    result.scalars.return_value = scalars
    fake_session.execute.return_value = result
    return AgentContext(session=fake_session, project_id=42)


def test_clickup_syncer_requires_project_id(fake_session) -> None:
    with pytest.raises(ClickupSyncerError, match="project_id"):
        ClickupSyncerAgent(client=MagicMock()).run(AgentContext(session=fake_session))


def test_clickup_syncer_skipped_without_client(fake_session, monkeypatch) -> None:
    monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
    ctx = _ctx_with_residuals(fake_session, [])
    result = ClickupSyncerAgent().run(ctx)
    assert result.outputs == {"skipped": True}
    assert "skipped" in result.summary.lower()


def test_clickup_syncer_creates_new_tasks(fake_session) -> None:
    fake_client = MagicMock()
    fake_client.create_task.return_value = {"id": "new-task-1"}
    fake_client.find_member.return_value = 11111111

    residual = _residual(assignee_hint="operador")
    ctx = _ctx_with_residuals(fake_session, [residual])

    result = ClickupSyncerAgent(client=fake_client).run(ctx)

    assert result.outputs["created"] == 1
    assert residual.clickup_task_id == "new-task-1"
    fake_client.create_task.assert_called_once()
    kwargs = fake_client.create_task.call_args.kwargs
    assert kwargs["assignees"] == [11111111]
    assert kwargs["priority"] == 2  # CLIENT_CONFIG → high


def test_clickup_syncer_closes_done_tasks(fake_session) -> None:
    fake_client = MagicMock()
    residual = _residual(clickup_task_id="abc", status=ResidualStatus.DONE)
    ctx = _ctx_with_residuals(fake_session, [residual])

    result = ClickupSyncerAgent(client=fake_client).run(ctx)
    assert result.outputs["closed"] == 1
    fake_client.close_task.assert_called_once_with("abc")


def test_clickup_syncer_updates_existing_open_tasks(fake_session) -> None:
    fake_client = MagicMock()
    residual = _residual(clickup_task_id="xyz", status=ResidualStatus.OPEN)
    ctx = _ctx_with_residuals(fake_session, [residual])

    result = ClickupSyncerAgent(client=fake_client).run(ctx)
    assert result.outputs["updated"] == 1
    fake_client.update_task.assert_called_once()


def test_clickup_syncer_collects_errors_as_warnings(fake_session) -> None:
    from wcm_worker.integrations.clickup import ClickupApiError

    fake_client = MagicMock()
    fake_client.create_task.side_effect = ClickupApiError(500, "boom")
    residual = _residual()
    ctx = _ctx_with_residuals(fake_session, [residual])

    result = ClickupSyncerAgent(client=fake_client).run(ctx)
    assert result.outputs["errors"] == 1
    assert result.outputs["created"] == 0
    assert result.warnings


def test_build_description_includes_metadata() -> None:
    r = _residual()
    r.screenshot_paths = ["/tmp/a.png", "/tmp/b.png"]
    body = _build_description(r)
    assert "Categoría" in body
    assert "30 min" in body
    assert "/tmp/a.png" in body
    assert "qa_runner" in body
