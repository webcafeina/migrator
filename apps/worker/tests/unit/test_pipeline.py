"""Tests del Orchestrator state machine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_types.enums import ProjectStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import (
    AgentNotImplementedError,
    BricksTranspilerError,
    UnrecoverableProjectError,
)
from wcm_worker.pipeline import Orchestrator, _PhaseSpec

# ---------- helpers ----------

class _StubAgent(BaseAgent):
    """Agent que devuelve un AgentResult fijo (configurable por tests)."""

    name = "stub"
    phase_name = "stub"
    _result: AgentResult = AgentResult(summary="stub ok")
    _raises: Exception | None = None

    def run(self, ctx: AgentContext) -> AgentResult:
        if self._raises is not None:
            raise self._raises
        return self._result


def _make_project_mock(*, has_ecommerce: bool = False, is_multilang: bool = False):
    p = MagicMock()
    p.id = 42
    p.has_ecommerce = has_ecommerce
    p.is_multilang = is_multilang
    p.status = ProjectStatus.QUEUED
    p.started_at = None
    p.completed_at = None
    return p


def _orch_with_phases(session: MagicMock, phases: tuple[_PhaseSpec, ...]) -> Orchestrator:
    return Orchestrator(session, phases=phases)


# ---------- tests ----------

def test_orchestrator_raises_if_project_missing(fake_session) -> None:
    fake_session.get.return_value = None
    orch = Orchestrator(fake_session, phases=())
    with pytest.raises(UnrecoverableProjectError):
        orch.run_project(42)


def test_orchestrator_runs_all_phases_in_order(fake_session) -> None:
    project = _make_project_mock()
    fake_session.get.return_value = project
    # `execute().scalar_one_or_none()` para ProjectPhase upsert → None (siempre nuevo)
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    class _A(_StubAgent): name = "a"; phase_name = "phase_a"
    class _B(_StubAgent): name = "b"; phase_name = "phase_b"

    orch = _orch_with_phases(fake_session, (
        _PhaseSpec("phase_a", _A),
        _PhaseSpec("phase_b", _B),
    ))
    outcome = orch.run_project(42)

    assert outcome.completed_phases == ["phase_a", "phase_b"]
    assert outcome.final_status == ProjectStatus.COMPLETED
    assert outcome.failed_phase is None


def test_orchestrator_skips_phase_on_not_implemented(fake_session) -> None:
    project = _make_project_mock()
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    class _NotImpl(_StubAgent):
        name = "notimpl"
        phase_name = "phase_notimpl"
        _raises = AgentNotImplementedError("stub WIP")

    class _After(_StubAgent): name = "after"; phase_name = "phase_after"

    orch = _orch_with_phases(fake_session, (
        _PhaseSpec("phase_notimpl", _NotImpl, required=False),
        _PhaseSpec("phase_after", _After),
    ))
    outcome = orch.run_project(42)

    assert "phase_notimpl" in outcome.skipped_phases
    assert "phase_after" in outcome.completed_phases
    assert outcome.final_status == ProjectStatus.COMPLETED


def test_orchestrator_required_phase_failure_blocks_pipeline(fake_session) -> None:
    project = _make_project_mock()
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    class _Bad(_StubAgent):
        name = "bad"
        phase_name = "phase_bad"
        _raises = BricksTranspilerError("transpiler explotó")

    class _After(_StubAgent): name = "after"; phase_name = "phase_after"

    orch = _orch_with_phases(fake_session, (
        _PhaseSpec("phase_bad", _Bad, required=True),
        _PhaseSpec("phase_after", _After),
    ))
    outcome = orch.run_project(42)

    assert outcome.failed_phase == "phase_bad"
    assert outcome.final_status == ProjectStatus.BLOCKED_HUMAN_INPUT
    assert "phase_after" not in outcome.completed_phases  # nunca llegó


def test_orchestrator_optional_phase_failure_continues(fake_session) -> None:
    project = _make_project_mock()
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    class _Bad(_StubAgent):
        name = "bad"
        phase_name = "phase_bad"
        _raises = BricksTranspilerError("optional fail")

    class _After(_StubAgent): name = "after"; phase_name = "phase_after"

    orch = _orch_with_phases(fake_session, (
        _PhaseSpec("phase_bad", _Bad, required=False),
        _PhaseSpec("phase_after", _After),
    ))
    outcome = orch.run_project(42)

    # phase_bad falló pero no era requerida → continúa con phase_after
    assert outcome.failed_phase == "phase_bad"
    assert "phase_after" in outcome.completed_phases
    assert outcome.final_status == ProjectStatus.QA_FAILED


def test_orchestrator_skips_phase_when_condition_false(fake_session) -> None:
    project = _make_project_mock(has_ecommerce=False)
    fake_session.get.return_value = project
    fake_session.execute.return_value.scalar_one_or_none.return_value = None

    class _Woo(_StubAgent): name = "woo"; phase_name = "phase_woo"

    orch = _orch_with_phases(fake_session, (
        _PhaseSpec("phase_woo", _Woo, condition_attr="has_ecommerce"),
    ))
    outcome = orch.run_project(42)

    assert "phase_woo" in outcome.skipped_phases
    assert "phase_woo" not in outcome.completed_phases
