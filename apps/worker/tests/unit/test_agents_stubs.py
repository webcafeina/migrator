"""Tests de los subagentes STUB.

Verifican que cada uno lanza AgentNotImplementedError con mensaje que
referencia la fase de implementación real. Si en el futuro se implementa
de verdad uno, el test correspondiente sirve de checklist (debe migrar
a tests funcionales).
"""

from __future__ import annotations

import pytest

from wcm_worker.agents import (
    WpmlConfiguratorAgent,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.errors import AgentNotImplementedError

# Promocionados a real (no son stubs):
# - Fase 9: ProspectorAgent, OutreachComposerAgent
# - Fase 10: ClickupSyncerAgent, ResendNotifierAgent, AssetOptimizerAgent
# - v0.16.0: VisualDiffAgent, QaRunnerAgent, ChecklistGeneratorAgent
# - v0.17.0: WooMigratorAgent, FormsRebuilderAgent
_STUB_AGENTS = [
    WpmlConfiguratorAgent,
]


@pytest.mark.parametrize("agent_cls", _STUB_AGENTS, ids=lambda c: c.__name__)
def test_stub_raises_not_implemented_with_clear_message(agent_cls, fake_session) -> None:
    agent = agent_cls()
    ctx = AgentContext(session=fake_session, project_id=1)
    with pytest.raises(AgentNotImplementedError) as exc_info:
        agent.run(ctx)
    msg = str(exc_info.value)
    # Cada mensaje debe identificar el agent y referenciar Fase X
    assert agent_cls.__name__ in msg, f"Mensaje no menciona {agent_cls.__name__}"
    assert "Fase" in msg or "pendiente" in msg
