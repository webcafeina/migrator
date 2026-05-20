"""Orchestrator del pipeline de migración.

State machine que recorre las fases del proyecto en orden, instancia
cada subagente, lo ejecuta, persiste el resultado en `project_phases` y
captura errores tipados decidiendo si reintentar / saltar / abortar.

Diseño en capas:
- `Orchestrator.run_project(project_id)` es el punto de entrada.
- Las fases son una lista declarativa `_DEFAULT_PHASES`. Cada entrada
  describe: `(phase_name, agent_class, required, condition_attr)`.
- `required=False` y/o `condition_attr` permiten saltar fases (visual-diff,
  woo-migrator, wpml-configurator).
- Errores: `AgentNotImplementedError` se trata como skip (warning), otros
  errores bloquean el pipeline y marcan la fase como FAILED.

Por qué no llamamos a otros Celery tasks desde aquí: lo hacemos
inline (sync) en el worker para mantener trazabilidad lineal en
project_phases y simplificar testing. Si una fase requiere paralelismo
intra-fase (p. ej. scraping de 200 páginas en paralelo), eso se gestiona
dentro del subagente.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from wcm_db.models.projects import Project, ProjectPhase
from wcm_types.enums import ProjectPhaseStatus, ProjectStatus
from wcm_worker.agents import (
    AssetOptimizerAgent,
    BaseAgent,
    BricksTranspilerAgent,
    ChecklistGeneratorAgent,
    ClickupSyncerAgent,
    ContentExtractorAgent,
    FormsRebuilderAgent,
    MultilangHandlerAgent,
    PreDeploySnapshotAgent,
    QaRunnerAgent,
    ResendNotifierAgent,
    ScraperOriginAgent,
    SeoPreserverAgent,
    VisualDiffAgent,
    WooMigratorAgent,
    WpDeployerAgent,
    WpmlConfiguratorAgent,
)
from wcm_worker.agents.base import AgentContext
from wcm_worker.errors import (
    AgentError,
    AgentNotImplementedError,
    UnrecoverableProjectError,
)
from wcm_worker.integrations.events import publish_phase_event

log = logging.getLogger("wcm.worker.pipeline")


@dataclass(frozen=True)
class _PhaseSpec:
    phase_name: str
    agent_class: type[BaseAgent]
    required: bool = True
    #: Nombre de atributo del Project que debe ser True para ejecutar esta
    #: fase. None = se ejecuta siempre. Ejemplos: "has_ecommerce",
    #: "is_multilang".
    condition_attr: str | None = None


#: Orden canónico de las fases de migración. Para campañas de prospección
#: hay otro flujo (ProspectorAgent + FingerprinterAgent + EnricherAgent +
#: OutreachComposerAgent), gestionado por tasks separadas.
_DEFAULT_PHASES: tuple[_PhaseSpec, ...] = (
    _PhaseSpec("scrape_origin", ScraperOriginAgent),
    _PhaseSpec("extract_content", ContentExtractorAgent),
    _PhaseSpec("preserve_seo", SeoPreserverAgent),
    _PhaseSpec("optimize_assets", AssetOptimizerAgent, required=False),
    _PhaseSpec("detect_multilang", MultilangHandlerAgent),
    _PhaseSpec("transpile_bricks", BricksTranspilerAgent),
    # ADR-042 — snapshot SQL del WP destino antes de modificarlo, para
    # poder rollback restaurando vía `wp db import`. required=True: sin
    # snapshot no se debe arrancar el deploy.
    _PhaseSpec("pre_deploy_snapshot", PreDeploySnapshotAgent),
    _PhaseSpec("deploy_wp", WpDeployerAgent),
    _PhaseSpec("migrate_woo", WooMigratorAgent, required=False, condition_attr="has_ecommerce"),
    _PhaseSpec("configure_wpml", WpmlConfiguratorAgent, required=False, condition_attr="is_multilang"),
    _PhaseSpec("rebuild_forms", FormsRebuilderAgent, required=False),
    _PhaseSpec("visual_diff", VisualDiffAgent, required=False),
    _PhaseSpec("qa", QaRunnerAgent, required=False),
    _PhaseSpec("generate_checklist", ChecklistGeneratorAgent, required=False),
    _PhaseSpec("sync_clickup", ClickupSyncerAgent, required=False),
    _PhaseSpec("notify", ResendNotifierAgent, required=False),
)


@dataclass
class OrchestrationOutcome:
    project_id: int
    completed_phases: list[str]
    skipped_phases: list[str]
    failed_phase: str | None = None
    final_status: ProjectStatus = ProjectStatus.RUNNING


class Orchestrator:
    """Recorre las fases del pipeline para un proyecto.

    Uso típico (desde Celery task):
        with session_scope() as session:
            outcome = Orchestrator(session).run_project(project_id)
    """

    def __init__(
        self,
        session: Session,
        *,
        phases: tuple[_PhaseSpec, ...] | None = None,
        resume: bool = False,
        force_rerun_all: bool = False,
    ) -> None:
        self.session = session
        self.phases = phases or _DEFAULT_PHASES
        self.resume = resume
        # ADR-043 — si force_rerun_all=True en un Resume, re-ejecuta TODA
        # la lista (comportamiento anterior). Si False (default), salta
        # las fases ya COMPLETED → Resume rápido.
        self.force_rerun_all = force_rerun_all

    def run_project(self, project_id: int) -> OrchestrationOutcome:
        project = self.session.get(Project, project_id)
        if project is None:
            raise UnrecoverableProjectError(f"Project {project_id} no existe")

        # Marcar como RUNNING. Si resume, intentar continuar desde la
        # primera fase no completada.
        project.status = ProjectStatus.RUNNING
        if not project.started_at:
            project.started_at = datetime.now(UTC)
        self.session.flush()

        outcome = OrchestrationOutcome(project_id=project_id, completed_phases=[], skipped_phases=[])

        for spec in self.phases:
            # ADR-043 — Resume rápido: si esta fase ya está COMPLETED en
            # un Resume sin force_rerun_all, la saltamos SIN tocar su
            # estado (sigue COMPLETED) y la contamos como completed_phases.
            if (
                self.resume
                and not self.force_rerun_all
                and self._is_already_completed(project_id, spec.phase_name)
            ):
                log.info(
                    "phase_skipped_already_completed_in_resume",
                    extra={"phase": spec.phase_name, "project_id": project_id},
                )
                outcome.completed_phases.append(spec.phase_name)
                continue

            if not self._should_run(spec, project):
                outcome.skipped_phases.append(spec.phase_name)
                self._mark_phase(project_id, spec.phase_name, ProjectPhaseStatus.SKIPPED, summary="condition no cumplida")
                continue

            try:
                self._run_phase(spec, project_id)
                # Cada fase es una unidad de trabajo que debe preservarse:
                # commit aquí evita que un fallo posterior arrastre con
                # rollback() el trabajo previo. Tras esto, rollback() solo
                # afecta a operaciones desde este punto, no a fases ya OK.
                self.session.commit()
                # Re-fetch del project tras commit (la sesión sigue la misma
                # pero los objetos pueden necesitar refresh para invalidar
                # cache local). Cubierto por el siguiente `session.get()`
                # en el próximo loop iter — no necesita acción explícita.
                outcome.completed_phases.append(spec.phase_name)
                project = self.session.get(Project, project_id)
            except AgentNotImplementedError as e:
                log.warning("phase_skipped_not_implemented", extra={
                    "phase": spec.phase_name, "reason": str(e)
                })
                self.session.rollback()
                self._mark_phase(project_id, spec.phase_name, ProjectPhaseStatus.SKIPPED, summary=str(e))
                self.session.commit()
                outcome.skipped_phases.append(spec.phase_name)
                project = self.session.get(Project, project_id)
            except AgentError as e:
                log.exception("phase_failed", extra={"phase": spec.phase_name})
                # Si el fallo ocurrió durante un flush, la session queda en
                # estado de rollback pendiente. Rollback restaura solo este
                # bloque (las fases previas hicieron commit y están a salvo).
                self.session.rollback()
                self._mark_phase(project_id, spec.phase_name, ProjectPhaseStatus.FAILED, summary=str(e))
                self.session.commit()
                outcome.failed_phase = spec.phase_name
                project = self.session.get(Project, project_id)
                if spec.required:
                    project.status = ProjectStatus.BLOCKED_HUMAN_INPUT
                    outcome.final_status = ProjectStatus.BLOCKED_HUMAN_INPUT
                    self.session.commit()
                    return outcome
                # Si no required, continúa con la siguiente fase
            except Exception as e:  # noqa: BLE001
                log.exception("phase_unexpected_error", extra={"phase": spec.phase_name})
                self.session.rollback()
                self._mark_phase(project_id, spec.phase_name, ProjectPhaseStatus.FAILED, summary=f"{type(e).__name__}: {e}")
                self.session.commit()
                outcome.failed_phase = spec.phase_name
                project = self.session.get(Project, project_id)
                # ADR-049 — el flag `required` gobierna lo que para o no,
                # no el tipo de excepción. En no-required, Exception genérica
                # se trata igual que AgentError: marca FAILED y sigue con la
                # siguiente fase. En required, mantiene comportamiento
                # conservador (BLOCKED + aborta).
                if spec.required:
                    project.status = ProjectStatus.BLOCKED_HUMAN_INPUT
                    outcome.final_status = ProjectStatus.BLOCKED_HUMAN_INPUT
                    self.session.commit()
                    return outcome

        # Si llegamos aquí sin failed_phase requerido, el proyecto se completa
        if outcome.failed_phase is None:
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.now(UTC)
            outcome.final_status = ProjectStatus.COMPLETED
        else:
            project.status = ProjectStatus.QA_FAILED
            outcome.final_status = ProjectStatus.QA_FAILED

        self.session.flush()
        return outcome

    # ---------- helpers ----------

    def _should_run(self, spec: _PhaseSpec, project: Project) -> bool:
        if spec.condition_attr is None:
            return True
        return bool(getattr(project, spec.condition_attr, False))

    def _is_already_completed(self, project_id: int, phase_name: str) -> bool:
        """ADR-043 — chequea si una fase ya está en estado COMPLETED.
        Usado por Resume rápido para saltar trabajo idempotente."""
        existing = self.session.execute(
            select(ProjectPhase).where(
                ProjectPhase.project_id == project_id,
                ProjectPhase.phase_name == phase_name,
            )
        ).scalar_one_or_none()
        return existing is not None and existing.status == ProjectPhaseStatus.COMPLETED

    def _run_phase(self, spec: _PhaseSpec, project_id: int) -> None:
        # Marcar phase como RUNNING antes de ejecutar
        self._mark_phase(project_id, spec.phase_name, ProjectPhaseStatus.RUNNING)

        agent = spec.agent_class()
        ctx = AgentContext(session=self.session, project_id=project_id)
        result = agent.run(ctx)

        # Marcar phase como COMPLETED con summary del agent
        self._mark_phase(
            project_id, spec.phase_name, ProjectPhaseStatus.COMPLETED,
            summary=result.summary, outputs=result.outputs,
        )

    def _mark_phase(
        self,
        project_id: int,
        phase_name: str,
        status: ProjectPhaseStatus,
        *,
        summary: str = "",
        outputs: dict | None = None,
    ) -> None:
        """Upsert por (project_id, phase_name). Idempotente."""
        existing = self.session.execute(
            select(ProjectPhase).where(
                ProjectPhase.project_id == project_id,
                ProjectPhase.phase_name == phase_name,
            )
        ).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is None:
            phase = ProjectPhase(
                project_id=project_id,
                phase_name=phase_name,
                status=status,
                started_at=now if status == ProjectPhaseStatus.RUNNING else None,
                completed_at=now if status in {ProjectPhaseStatus.COMPLETED, ProjectPhaseStatus.SKIPPED, ProjectPhaseStatus.FAILED} else None,
                attempt=1,
                output_summary={"summary": summary, "outputs": outputs or {}},
            )
            if status == ProjectPhaseStatus.FAILED:
                phase.error_log = summary
            self.session.add(phase)
        else:
            existing.status = status
            existing.attempt += 1
            if status == ProjectPhaseStatus.RUNNING:
                existing.started_at = now
            if status in {ProjectPhaseStatus.COMPLETED, ProjectPhaseStatus.SKIPPED, ProjectPhaseStatus.FAILED}:
                existing.completed_at = now
            existing.output_summary = {"summary": summary, "outputs": outputs or {}}
            if status == ProjectPhaseStatus.FAILED:
                existing.error_log = summary

        self.session.flush()

        # v0.19.0 — publica al canal Redis SSE. Silencioso si Redis falla
        # (el pipeline NO depende de la disponibilidad del canal).
        publish_phase_event(
            project_id=project_id,
            phase_name=phase_name,
            status=status.value if hasattr(status, "value") else str(status),
            summary=summary,
        )
