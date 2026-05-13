"""Interfaz base para todos los subagentes.

Diseño:
- Cada subagente extiende `BaseAgent` y sobrescribe `run(ctx) -> AgentResult`.
- `AgentContext` lleva la sesión DB + el ID del proyecto + flags
  específicos por fase. Inmutable.
- `AgentResult` lleva summary + outputs + errores no bloqueantes.
- Los errores graves se propagan como excepciones (jerarquía en
  `wcm_worker.errors`).

Por qué no usamos los `.claude/agents/*.md` como interfaz: esos son
descriptors para Claude Code (durante construcción). Estos son las
implementaciones runtime del producto. Comparten la nomenclatura pero
viven en planos distintos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session


@dataclass
class AgentContext:
    """Contexto pasado al agent en cada `run`. Inmutable por convención."""

    session: Session
    project_id: int | None = None
    lead_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Resultado canónico del `run` de un agent.

    `outputs` es libre por agent — el orchestrator solo lo persiste en
    `project_phases.output_summary` para diagnóstico. `warnings` lleva
    issues no bloqueantes (p. ej. bloques `unknown` que generaron tareas
    residuales).
    """

    summary: str = ""
    outputs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    residual_tasks_created: int = 0


class BaseAgent(ABC):
    """Interfaz común. Cada subagente define su `name` y un `run`."""

    name: str = "base"
    phase_name: str = "base"

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        """Ejecuta el subagente. Lanza error tipado en caso de fallo."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
