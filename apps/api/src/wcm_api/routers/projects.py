"""Endpoints de proyectos de migración + fases.

Operaciones expuestas:
- list / get / create / update
- start (lanza el pipeline en worker)
- resume (reanuda tras error)
- cancel (marca cancelado, NO interrumpe job en vuelo, eso es Fase 6)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.security import require_role
from wcm_api.services.events import subscribe_to_project_events
from wcm_api.services.preflight import run_preflight, serialize_preflight_for_db
from wcm_api.services.source_credentials import (
    FernetNotConfiguredError,
    encrypt_source_credentials,
)
from wcm_api.tasks.enqueue import (
    enqueue_project_pipeline,
    enqueue_project_publish,
    enqueue_project_rollback,
)
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.leads import Lead
from wcm_db.models.projects import Project, ProjectPhase
from wcm_db.models.qa_reports import QaReport
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.visual_diffs import VisualDiff
from wcm_types.enums import (
    BuilderType,
    ProjectPhaseStatus,
    ProjectStatus,
    ResidualStatus,
    UserRole,
)
from wcm_types.schemas.projects import (
    PreflightResult,
    ProjectCreate,
    ProjectPhaseRead,
    ProjectRead,
    ProjectUpdate,
    SourceCredentialsUpdate,
)
from wcm_types.schemas.qa_reports import QaReportRead
from wcm_types.schemas.visual_diffs import (
    VisualDiffRead,
    VisualDiffsListResponse,
)

log = logging.getLogger("wcm.api.projects")

router = APIRouter(prefix="/projects", tags=["projects"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)
_admin_only = require_role(UserRole.ADMIN.value)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    project_status: ProjectStatus | None = None,
) -> list[ProjectRead]:
    stmt = select(Project).order_by(Project.created_at.desc())
    if project_status:
        stmt = stmt.where(Project.status == project_status)
    items = (await session.execute(stmt)).scalars().all()
    return [ProjectRead.model_validate(p) for p in items]


class ProjectStats(BaseModel):
    """Agregados de proyectos para el topbar del rediseño /projects.

    Distingue 6 buckets de estado (los del enum `ProjectStatus`) +
    `failed_or_cancelled` agregado para el topbar (no merece celda
    separada). `avg_visual_diff_score` excluye los `null` (proyectos
    sin diff calculado todavía).
    """

    total: int = Field(description="Proyectos totales.")
    queued: int = Field(description="Proyectos encolados sin arrancar.")
    running: int = Field(description="Proyectos con pipeline en curso.")
    blocked: int = Field(description="Bloqueados esperando input humano.")
    completed: int = Field(description="Migraciones cerradas con éxito.")
    failed_or_cancelled: int = Field(description="QA fallido o cancelados manualmente.")
    distinct_builders: int = Field(
        description="Builders origen únicos detectados, sin unknown/null."
    )
    avg_visual_diff_score: float | None = Field(
        description="Score medio de visual diff (0..1). null si ningún proyecto tiene diff."
    )


@router.get("/stats", response_model=ProjectStats)
async def project_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> ProjectStats:
    """Devuelve agregados de proyectos para el topbar de `/projects`.

    8 buckets calculados en SQL separado para mantener legibilidad.
    Tabla pequeña en MVP (<100 proyectos esperados); cuando crezca
    consideraremos un único GROUP BY.
    """
    total = (await session.execute(select(func.count()).select_from(Project))).scalar_one()
    queued = (
        await session.execute(
            select(func.count()).select_from(Project).where(Project.status == ProjectStatus.QUEUED)
        )
    ).scalar_one()
    running = (
        await session.execute(
            select(func.count()).select_from(Project).where(Project.status == ProjectStatus.RUNNING)
        )
    ).scalar_one()
    blocked = (
        await session.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.status == ProjectStatus.BLOCKED_HUMAN_INPUT)
        )
    ).scalar_one()
    completed = (
        await session.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.status == ProjectStatus.COMPLETED)
        )
    ).scalar_one()
    failed_or_cancelled = (
        await session.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.status.in_([ProjectStatus.QA_FAILED, ProjectStatus.CANCELLED]))
        )
    ).scalar_one()
    distinct_builders = (
        await session.execute(
            select(func.count(func.distinct(Project.builder_source)))
            .where(Project.builder_source.is_not(None))
            .where(Project.builder_source != BuilderType.UNKNOWN)
        )
    ).scalar_one()
    avg_diff = (
        await session.execute(
            select(func.avg(Project.visual_diff_avg_score)).where(
                Project.visual_diff_avg_score.is_not(None)
            )
        )
    ).scalar_one_or_none()
    return ProjectStats(
        total=int(total),
        queued=int(queued),
        running=int(running),
        blocked=int(blocked),
        completed=int(completed),
        failed_or_cancelled=int(failed_or_cancelled),
        distinct_builders=int(distinct_builders),
        avg_visual_diff_score=float(avg_diff) if avg_diff is not None else None,
    )


class ProjectFleetItem(BaseModel):
    """v0.19.0 — vista compacta de cada proyecto para la grid fleet.

    Agrega el estado de las 15 fases en 5 buckets de alto nivel para
    pintar un mini-stepper de 5 dots por proyecto sin N+1 fetches.
    """

    id: int
    client_name: str
    source_url: str
    target_domain: str | None
    builder_source: BuilderType | None
    status: ProjectStatus
    visual_diff_avg_score: float | None
    has_ecommerce: bool
    is_multilang: bool
    started_at: datetime | None
    phase_summary: dict[str, str] = Field(
        description="{scrape, transpile, deploy, qa, notify} con status agregado por bucket."
    )
    current_phase_name: str | None = Field(
        description="Última fase RUNNING/COMPLETED para diagnóstico rápido."
    )


#: Mapping de fase canónica → bucket de alto nivel para vista fleet.
_PHASE_BUCKETS: dict[str, str] = {
    "scrape_origin": "scrape",
    "extract_content": "scrape",
    "preserve_seo": "scrape",
    "optimize_assets": "scrape",
    "detect_multilang": "scrape",
    "transpile_bricks": "transpile",
    "deploy_wp": "deploy",
    "migrate_woo": "deploy",
    "configure_wpml": "deploy",
    "rebuild_forms": "deploy",
    "visual_diff": "qa",
    "qa": "qa",
    "generate_checklist": "notify",
    "sync_clickup": "notify",
    "notify": "notify",
    "rollback": "notify",
}
_BUCKET_ORDER: list[str] = ["scrape", "transpile", "deploy", "qa", "notify"]


def _aggregate_bucket_status(phase_statuses: list[str]) -> str:
    """Reduce los status de las fases de un bucket a UN solo status.

    Prioridades: failed > running > pending > completed (todas) > skipped.
    """
    if not phase_statuses:
        return "pending"
    if any(s == "failed" for s in phase_statuses):
        return "failed"
    if any(s == "running" for s in phase_statuses):
        return "running"
    if all(s in ("completed", "skipped") for s in phase_statuses):
        return "completed" if any(s == "completed" for s in phase_statuses) else "skipped"
    return "pending"


@router.get("/fleet", response_model=list[ProjectFleetItem])
async def projects_fleet(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> list[ProjectFleetItem]:
    """v0.19.0 — listado enriquecido para la vista fleet del dashboard.

    Devuelve TODOS los proyectos con phase_summary pre-agregada en
    5 buckets de alto nivel. Una sola query para evitar N+1 fetches
    del cliente. Para >50 proyectos, considerar paginación en v0.20.0.
    """
    stmt_projects = select(Project).order_by(Project.created_at.desc())
    projects = list((await session.execute(stmt_projects)).scalars().all())
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    stmt_phases = (
        select(ProjectPhase.project_id, ProjectPhase.phase_name, ProjectPhase.status)
        .where(ProjectPhase.project_id.in_(project_ids))
    )
    phase_rows = (await session.execute(stmt_phases)).all()

    by_project: dict[int, dict[str, list[str]]] = {pid: {} for pid in project_ids}
    current_phase: dict[int, str | None] = {pid: None for pid in project_ids}
    for pid, phase_name, ph_status in phase_rows:
        s_val = ph_status.value if hasattr(ph_status, "value") else str(ph_status)
        bucket = _PHASE_BUCKETS.get(phase_name, "notify")
        by_project[pid].setdefault(bucket, []).append(s_val)
        if s_val in ("running", "completed"):
            current_phase[pid] = phase_name

    items: list[ProjectFleetItem] = []
    for p in projects:
        buckets = by_project.get(p.id, {})
        phase_summary = {
            b: _aggregate_bucket_status(buckets.get(b, [])) for b in _BUCKET_ORDER
        }
        items.append(
            ProjectFleetItem(
                id=p.id,
                client_name=p.client_name,
                source_url=p.source_url,
                target_domain=p.target_domain,
                builder_source=p.builder_source,
                status=p.status,
                visual_diff_avg_score=p.visual_diff_avg_score,
                has_ecommerce=p.has_ecommerce,
                is_multilang=p.is_multilang,
                started_at=p.started_at,
                phase_summary=phase_summary,
                current_phase_name=current_phase.get(p.id),
            )
        )
    return items


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> ProjectRead:
    data = payload.model_dump(exclude_none=True)
    # HttpUrl → str
    if "source_url" in data:
        data["source_url"] = str(data["source_url"])
    project = Project(**data)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


class ProjectWithStartPayload(BaseModel):
    """Payload del endpoint combinado `POST /projects/with-start` (ADR-047).

    Extiende `ProjectCreate` con 2 flags para scripts/webhooks:
    - `skip_preflight`: salta el preflight (útil si ya se validó externamente).
    - `force_start`: arranca aunque el preflight tenga bloqueantes (escape
      para casos donde el preflight tiene falso positivo).

    Ambos flags son peligrosos — solo usar en scripts conscientes.
    """

    # Reutilizamos ProjectCreate vía composición en lugar de herencia para
    # que el schema OpenAPI muestre claramente los 2 flags adicionales.
    model_config = {"extra": "allow"}
    skip_preflight: bool = Field(
        default=False,
        description="Si True, salta el preflight antes de arrancar (peligroso).",
    )
    force_start: bool = Field(
        default=False,
        description="Si True, arranca aunque preflight tenga bloqueantes (peligroso).",
    )


@router.post(
    "/with-start",
    status_code=status.HTTP_200_OK,
    description=(
        "ADR-047 — Combinador para scripts/webhooks/integraciones. Crea el "
        "proyecto y opcionalmente lo arranca tras preflight. NO se usa "
        "desde la UI (la UI sigue 3 botones explícitos en el wizard)."
    ),
)
async def create_project_with_start(
    payload: dict,  # validamos manualmente para combinar ProjectCreate + flags
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    # Separar flags de ProjectCreate
    skip_preflight = bool(payload.pop("skip_preflight", False))
    force_start = bool(payload.pop("force_start", False))

    # Validar ProjectCreate con el resto del payload
    try:
        project_create = ProjectCreate.model_validate(payload)
    except Exception as e:  # pydantic ValidationError
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(e)) from e

    # 1. Crear el proyecto
    data = project_create.model_dump(exclude_none=True)
    if "source_url" in data:
        data["source_url"] = str(data["source_url"])
    project = Project(**data)
    session.add(project)
    await session.commit()
    await session.refresh(project)

    response_base = {
        "project_id": project.id,
        "project": ProjectRead.model_validate(project).model_dump(mode="json"),
    }

    # 2. Preflight (a menos que skip)
    preflight_dict: dict | None = None
    if not skip_preflight:
        preflight = await run_preflight(project)
        project.preflight_results_json = serialize_preflight_for_db(preflight)
        project.preflight_at = preflight.executed_at
        preflight_dict = preflight.model_dump(mode="json")

        if not preflight.can_start and not force_start:
            # 409 con preflight detallado; proyecto YA está creado
            # (queda en queued) — el script puede consultar o eliminar.
            await session.commit()
            from fastapi import HTTPException

            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Preflight bloqueante; usa force_start=true si entiendes "
                        "el riesgo, o resuelve los bloqueantes y vuelve a intentar."
                    ),
                    "project_id": project.id,
                    "preflight": preflight_dict,
                },
            )

    # 3. Arrancar el pipeline
    project.status = ProjectStatus.RUNNING
    project.started_at = datetime.now(UTC)
    await session.commit()
    task_id = enqueue_project_pipeline(project.id, resume=False)

    return {
        **response_base,
        "task_id": task_id,
        "status": "queued",
        "preflight": preflight_dict,
    }


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> ProjectRead:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    return ProjectRead.model_validate(project)


class LeadOriginSummary(BaseModel):
    """Vista reducida del lead origen del que nació el proyecto."""

    id: int
    business_name: str | None
    score: int
    builder_detected: BuilderType | None


class ProjectSummary(BaseModel):
    """Resumen agregado del proyecto para el header del rediseño
    `/projects/[id]`. Evita 3-4 fetches del cliente (project + phases +
    residual_tasks + lead) reduciéndolos a 2 (`/projects/{id}` para los
    campos completos editables + `/summary` para los agregados).

    `current_phase_name` es la fase RUNNING actual; si no hay ninguna,
    devuelve la última COMPLETED como contexto. None si no hay fases.
    """

    project_id: int
    lead_origin: LeadOriginSummary | None

    phases_total: int
    phases_completed: int
    phases_failed: int
    phases_running: int
    phases_pending: int
    current_phase_name: str | None

    residual_total: int
    residual_open: int
    residual_done: int

    # ADR-052 — páginas con "muchos UNKNOWN": >= 3 absolutos Y >= 50%
    # del total de bloques de la página. Calculado on-the-fly desde
    # content_blocks. UI muestra badge ámbar en header si > 0.
    pages_with_many_unknowns: int = 0


@router.get("/{project_id}/summary", response_model=ProjectSummary)
async def project_summary(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> ProjectSummary:
    """Agregados del proyecto: progreso de fases, lead origen, residuales."""
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    # Lead origen — None si lead_id es null o el lead fue borrado
    # (ondelete=SET NULL).
    lead_origin: LeadOriginSummary | None = None
    if project.lead_id is not None:
        lead = await session.get(Lead, project.lead_id)
        if lead is not None:
            lead_origin = LeadOriginSummary(
                id=lead.id,
                business_name=lead.business_name,
                score=lead.score,
                builder_detected=lead.builder_detected,
            )

    # Fases: counts agrupados por status.
    phase_rows = (
        await session.execute(
            select(ProjectPhase.status, func.count())
            .where(ProjectPhase.project_id == project_id)
            .group_by(ProjectPhase.status)
        )
    ).all()
    by_status: dict[ProjectPhaseStatus, int] = {s: c for s, c in phase_rows}
    phases_total = sum(by_status.values())
    phases_completed = by_status.get(ProjectPhaseStatus.COMPLETED, 0)
    phases_failed = by_status.get(ProjectPhaseStatus.FAILED, 0)
    phases_running = by_status.get(ProjectPhaseStatus.RUNNING, 0)
    phases_pending = by_status.get(ProjectPhaseStatus.PENDING, 0)

    # Fase actual: RUNNING si hay, sino última COMPLETED.
    current_phase_name: str | None = None
    if phases_running > 0:
        row = (
            await session.execute(
                select(ProjectPhase.phase_name)
                .where(ProjectPhase.project_id == project_id)
                .where(ProjectPhase.status == ProjectPhaseStatus.RUNNING)
                .order_by(ProjectPhase.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        current_phase_name = row
    elif phases_completed > 0:
        row = (
            await session.execute(
                select(ProjectPhase.phase_name)
                .where(ProjectPhase.project_id == project_id)
                .where(ProjectPhase.status == ProjectPhaseStatus.COMPLETED)
                .order_by(ProjectPhase.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        current_phase_name = row

    # Residual tasks counts.
    residual_rows = (
        await session.execute(
            select(ResidualTask.status, func.count())
            .where(ResidualTask.project_id == project_id)
            .group_by(ResidualTask.status)
        )
    ).all()
    residual_by: dict[ResidualStatus, int] = {s: c for s, c in residual_rows}
    residual_total = sum(residual_by.values())
    residual_done = residual_by.get(ResidualStatus.DONE, 0)
    # "Abiertos" = todo lo que NO está done/skipped. Operativamente lo
    # que el operador aún tiene que tocar.
    residual_open = residual_total - residual_done - residual_by.get(ResidualStatus.SKIPPED, 0)

    # ADR-052 — páginas con "muchos UNKNOWN": agregación por page_id
    # con doble criterio (>= 3 absolutos Y >= 50% del total). Sin tabla
    # nueva — query barata sobre content_blocks.
    unknown_subq = (
        select(
            ContentBlock.page_id.label("page_id"),
            func.count().filter(ContentBlock.block_type == "unknown").label("unknown_count"),
            func.count().label("total"),
        )
        .where(ContentBlock.project_id == project_id)
        .group_by(ContentBlock.page_id)
        .having(func.count().filter(ContentBlock.block_type == "unknown") >= 3)
        .having(
            func.count().filter(ContentBlock.block_type == "unknown") * 1.0
            / func.count()
            >= 0.5
        )
        .subquery()
    )
    pages_with_many_unknowns = (
        await session.execute(select(func.count()).select_from(unknown_subq))
    ).scalar_one()

    return ProjectSummary(
        project_id=project.id,
        lead_origin=lead_origin,
        phases_total=phases_total,
        phases_completed=phases_completed,
        phases_failed=phases_failed,
        phases_running=phases_running,
        phases_pending=phases_pending,
        current_phase_name=current_phase_name,
        residual_total=residual_total,
        residual_open=residual_open,
        residual_done=residual_done,
        pages_with_many_unknowns=int(pages_with_many_unknowns or 0),
    )


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> ProjectRead:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(project, k, v)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """Arranca el pipeline de migración. ADR-048: re-ejecuta SIEMPRE el
    preflight antes de encolar — invariante "el pipeline NUNCA arranca
    sin preflight fresh OK". Si `can_start=False` → 409 con detalle,
    proyecto queda en `queued`.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if project.status == ProjectStatus.RUNNING:
        raise ConflictError(f"Project {project_id} ya está en ejecución")

    # ADR-048 — re-ejecutar preflight antes de cada Start
    preflight = await run_preflight(project)
    project.preflight_results_json = serialize_preflight_for_db(preflight)
    project.preflight_at = preflight.executed_at

    if not preflight.can_start:
        await session.commit()  # persiste el preflight actualizado
        raise ConflictError(
            "Preflight bloqueante: "
            + "; ".join(preflight.blocking_issues)
            + ". Resuelve los issues y vuelve a intentar."
        )

    project.status = ProjectStatus.RUNNING
    project.started_at = datetime.now(UTC)
    await session.commit()
    task_id = enqueue_project_pipeline(project_id, resume=False)
    return {"task_id": task_id, "status": "queued", "project_id": project_id}


@router.post("/{project_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
    force_rerun_all: bool = Query(
        default=False,
        description=(
            "ADR-043 — Si True, re-ejecuta TODAS las fases (incluso "
            "COMPLETED). Si False (default), Resume rápido salta las "
            "ya completed. Útil si sospechas que una fase COMPLETED "
            "dejó algo inconsistente (raro)."
        ),
    ),
) -> dict:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    project.status = ProjectStatus.RUNNING
    await session.commit()
    task_id = enqueue_project_pipeline(
        project_id, resume=True, force_rerun_all=force_rerun_all
    )
    return {
        "task_id": task_id,
        "status": "queued",
        "project_id": project_id,
        "resume": True,
        "force_rerun_all": force_rerun_all,
    }


@router.post("/{project_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """Marca el proyecto como cancelado. NO interrumpe el job en vuelo
    (Fase 6 añadirá señalización Celery). El próximo paso del worker
    comprobará el estado y abortará grácilmente.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    project.status = ProjectStatus.CANCELLED
    await session.commit()
    return {"status": "cancelled", "project_id": project_id}


@router.post("/{project_id}/rollback", status_code=status.HTTP_202_ACCEPTED)
async def rollback_project(
    project_id: int,
    payload: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.19.0 — deshace el deploy borrando las páginas WP creadas.

    Requiere body `{"confirm": true}` para evitar disparos accidentales
    (es destructivo). Solo permitido si status ∈ {qa_failed, completed,
    blocked_human_input}. Marca el proyecto como ROLLED_BACK al terminar.
    """
    if not payload.get("confirm"):
        raise ConflictError(
            "Rollback es destructivo. Envía `{\"confirm\": true}` para confirmar."
        )
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    allowed = {
        ProjectStatus.QA_FAILED,
        ProjectStatus.COMPLETED,
        ProjectStatus.BLOCKED_HUMAN_INPUT,
    }
    if project.status not in allowed:
        raise ConflictError(
            f"Rollback solo permitido si status ∈ {{qa_failed, completed, "
            f"blocked_human_input}}. Estado actual: {project.status.value}."
        )
    task_id = enqueue_project_rollback(project_id)
    return {"task_id": task_id, "status": "queued", "project_id": project_id}


@router.post("/{project_id}/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.20.0 (ADR-039) — pone todas las páginas migradas en status=publish.

    Disparable por el operador tras validar visual diff + QA en draft.
    No es destructivo (publicar es reversible vía POST de nuevo con
    {status: draft}). Solo permitido si status ∈ {completed, qa_failed}.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    allowed = {ProjectStatus.COMPLETED, ProjectStatus.QA_FAILED}
    if project.status not in allowed:
        raise ConflictError(
            f"Publish solo permitido si status ∈ {{completed, qa_failed}}. "
            f"Estado actual: {project.status.value}."
        )
    task_id = enqueue_project_publish(project_id)
    return {"task_id": task_id, "status": "queued", "project_id": project_id}


@router.post("/{project_id}/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_project(
    project_id: int,
    payload: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """ADR-041 — Re-arranca un proyecto que está en ROLLED_BACK.

    Resetea timestamps + cambia status a QUEUED + encola pipeline
    completo. NO borra historial (visual_diffs, qa_reports, residual_tasks,
    bricks_pages.bricks_json conservados — útiles para diagnóstico
    comparativo entre intentos).

    Requiere body `{"confirm": true}`. Solo permitido si status =
    ROLLED_BACK (409 cualquier otro).
    """
    if not payload.get("confirm"):
        raise ConflictError(
            'Re-arranque requiere `{"confirm": true}` en el body.'
        )
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if project.status != ProjectStatus.ROLLED_BACK:
        raise ConflictError(
            f"Re-arranque solo permitido si status=rolled_back. "
            f"Estado actual: {project.status.value}."
        )
    # Reset timestamps + status. No tocamos bricks_pages.bricks_json
    # (lo conservamos para que el próximo pipeline lo UPSERT si scrape
    # detecta cambios). visual_diffs/qa_reports/residual_tasks
    # también se conservan para diagnóstico comparativo.
    project.status = ProjectStatus.QUEUED
    project.started_at = None
    project.completed_at = None
    await session.commit()
    task_id = enqueue_project_pipeline(project_id, resume=False)
    return {
        "task_id": task_id,
        "status": "queued",
        "project_id": project_id,
        "restarted": True,
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    payload: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> Response:
    """ADR-054 — Borrar proyecto + datos asociados en cascada.

    Admin-only. Requiere body `{"confirm": "DELETE PROJECT N"}` literal
    (texto exacto incluyendo el ID) — protege contra borrar el equivocado.

    Pasos:
    1. Audit log entry con datos preservados (trazabilidad post-delete).
    2. Limpieza R2: borra todos los objetos bajo `projects/{id}/` (assets
       optimizados, screenshots visual_diff, checklists PDF/MD). Failsafe
       no levanta — si R2 falla, el delete BD sigue adelante.
    3. CASCADE delete BD — todas las tablas relacionadas con FK
       ON DELETE CASCADE se vacían (scraped_pages, content_blocks,
       bricks_pages, assets, woo_products, woo_orders, visual_diffs,
       qa_reports, residual_tasks, project_phases, seo_redirects).

    NOTA: NO ejecuta rollback inline si status != ROLLED_BACK. El operador
    debería hacer rollback primero si quiere limpiar también el WP destino.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if project.status == ProjectStatus.RUNNING:
        raise ConflictError(
            "No se puede borrar un proyecto en ejecución. Cancela primero."
        )

    expected_confirm = f"DELETE PROJECT {project_id}"
    actual_confirm = payload.get("confirm", "")
    if actual_confirm != expected_confirm:
        raise ConflictError(
            f'Borrado requiere body {{"confirm": "{expected_confirm}"}} literal '
            "(texto exacto incluyendo el ID). Protege contra borrar el "
            "equivocado por error."
        )

    # Audit: log structlog estructurado con datos preservados (la fila
    # del audit_log NO se borra en CASCADE). Para v0.20.0+ se reemplaza
    # por entry en tabla audit_log via wcm_db.models.AuditLog (ADR-054
    # tarea #101 service cascade).
    log.warning(
        "project_deleted",
        extra={
            "project_id": project.id,
            "client_name": project.client_name,
            "source_url": project.source_url,
            "target_domain": project.target_domain,
            "status_at_delete": project.status.value,
        },
    )

    # Limpieza R2 antes del CASCADE BD. Failsafe: si falla, log warning y
    # seguimos — un huérfano R2 acumulable es preferible a un proyecto
    # parcialmente borrado.
    from wcm_api.services.project_cleanup import delete_project_r2_assets
    r2_result = delete_project_r2_assets(project_id)
    log.info(
        "project_delete_r2_cleanup",
        extra={"project_id": project_id, "r2_result": r2_result},
    )

    # CASCADE delete — todas las tablas con FK ondelete=CASCADE se vacían.
    await session.delete(project)
    await session.commit()
    return Response(status_code=204)


@router.get("/{project_id}/phases", response_model=list[ProjectPhaseRead])
async def list_project_phases(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> list[ProjectPhaseRead]:
    stmt = (
        select(ProjectPhase)
        .where(ProjectPhase.project_id == project_id)
        .order_by(ProjectPhase.created_at.asc())
    )
    phases = (await session.execute(stmt)).scalars().all()
    return [ProjectPhaseRead.model_validate(p) for p in phases]


@router.get("/{project_id}/visual-diffs", response_model=VisualDiffsListResponse)
async def list_visual_diffs(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> VisualDiffsListResponse:
    """Lista comparaciones visuales página-a-página del proyecto (v0.16.0).

    Alimenta `/projects/[id]/diff` del dashboard. Cada fila apunta a
    3 PNG en R2 (origen, destino, overlay) + score 0-1. `avg_score`
    es el promedio de scores no-nulos del proyecto.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    stmt = (
        select(VisualDiff)
        .where(VisualDiff.project_id == project_id)
        .order_by(VisualDiff.page_path.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    pages = [VisualDiffRead.model_validate(r) for r in rows]
    return VisualDiffsListResponse(
        project_id=project_id,
        avg_score=project.visual_diff_avg_score,
        pages_total=len(pages),
        pages=pages,
    )


@router.get("/{project_id}/qa-report", response_model=QaReportRead | None)
async def get_latest_qa_report(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> QaReportRead | None:
    """Última fila `qa_reports` del proyecto (v0.16.0).

    Alimenta `/projects/[id]/qa` del dashboard. Devuelve `null` si el
    agent qa-runner aún no ejecutó (status 200 con body `null`).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    stmt = (
        select(QaReport)
        .where(QaReport.project_id == project_id)
        .order_by(QaReport.created_at.desc())
        .limit(1)
    )
    report = (await session.execute(stmt)).scalar_one_or_none()
    if report is None:
        return None
    return QaReportRead.model_validate(report)


@router.get("/{project_id}/checklist/download")
async def download_checklist(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    format: Annotated[str, Query(pattern="^(pdf|md)$")] = "pdf",
) -> Response:
    """Descarga el entregable del checklist (v0.16.0).

    Comportamiento:
    - URL es HTTPS (R2 público) → 302 redirect al cliente.
    - URL es `file://` (R2 no configurado, fallback dev) → stream del
      fichero local con content-type apropiado.
    - URL es `null` (agent aún no ejecutado o falló) → 404.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    url = project.checklist_pdf_url if format == "pdf" else project.checklist_md_url
    if not url:
        raise NotFoundError(
            f"Checklist {format} aún no generado para project {project_id}. "
            "Re-ejecuta el pipeline o el agent checklist-generator."
        )

    if url.startswith(("http://", "https://")):
        return RedirectResponse(url=url, status_code=302)

    # Fallback dev: file:// → stream local.
    if url.startswith("file://"):
        path = url[len("file://") :]
        try:
            with open(path, "rb") as f:
                content = f.read()
        except OSError as e:
            raise NotFoundError(f"Fichero local no accesible: {path} ({e})") from e
        media_type = "application/pdf" if format == "pdf" else "text/markdown"
        filename = f"checklist-project-{project_id}.{format}"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise NotFoundError(f"URL del checklist no reconocida: {url[:60]}")


# ---------- v0.18.0: preflight + source credentials ----------


@router.post("/{project_id}/preflight", response_model=PreflightResult)
async def preflight_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> PreflightResult:
    """Ejecuta los 4 chequeos pre-Start del proyecto y persiste el
    resultado en `projects.preflight_results_json` + `preflight_at`
    para cache client-side.

    Los 4 chequeos:
    1. WP destino accesible (REST + SSH) — BLOQUEA si falla.
    2. Plugins detectados (Bricks/GF/WC) — informativo.
    3. Origen accesible — BLOQUEA si 4xx/5xx.
    4. Credenciales del origen (si configuradas) — warning, NO bloquea.

    Cada chequeo tiene timeout 10s. Ejecutados en paralelo (~10s total).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    result = await run_preflight(project)
    project.preflight_results_json = serialize_preflight_for_db(result)
    project.preflight_at = result.executed_at
    await session.commit()
    return result


@router.put("/{project_id}/source-credentials", response_model=ProjectRead)
async def put_source_credentials(
    project_id: int,
    payload: SourceCredentialsUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> ProjectRead:
    """Guarda credenciales del back del origen cifradas con Fernet.

    Admin-only — son secretos. El endpoint nunca devuelve las
    credenciales en claro; `ProjectRead.has_source_credentials` solo
    indica si están configuradas.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    payload_dict = payload.model_dump()
    builder = payload_dict.pop("builder")
    # Sanity: el builder del payload debe coincidir con el del proyecto
    # (si está fijado). Evita configurar Wix por error en un proyecto Webflow.
    if project.builder_source and project.builder_source.value != builder:
        raise ConflictError(
            f"El proyecto tiene builder_source={project.builder_source.value} "
            f"pero las credenciales son para builder={builder}."
        )

    try:
        encrypted = encrypt_source_credentials(payload_dict)
    except FernetNotConfiguredError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(e)) from e

    project.source_credentials_encrypted = encrypted
    project.source_access_mode = "api"
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}/source-credentials", status_code=204)
async def delete_source_credentials(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> Response:
    """Borra las credenciales del back del origen y vuelve a modo `none`."""
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    project.source_credentials_encrypted = None
    project.source_access_mode = "none"
    await session.commit()
    return Response(status_code=204)


# ---------- v0.19.0: SSE events ----------


@router.get("/{project_id}/events")
async def project_events(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> StreamingResponse:
    """SSE — stream-ea cambios de fase del pipeline en tiempo real.

    El cliente conecta con `EventSource('/api/v1/projects/{id}/events')`.
    Cada evento llega como `data: <json>\\n\\n` y el cliente llama
    `router.refresh()` para re-fetchar.

    Si Redis no responde → 503 (cliente cae a polling 2s).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    try:
        # Verificación temprana de la conexión Redis (lazy en el generator,
        # pero queremos 503 inmediato si falla la subscripción inicial).
        stream = subscribe_to_project_events(project_id)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx: no bufferear
            "Connection": "keep-alive",
        },
    )


