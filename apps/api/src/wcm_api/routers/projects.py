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
from typing import Annotated, Any, Literal

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
    enqueue_brief_suggest_refinements,
    enqueue_preview_regenerate_page,
    enqueue_project_pipeline,
    enqueue_project_publish,
    enqueue_project_rollback,
)
from wcm_db.models.assets import Asset
from wcm_db.models.bricks_pages import BricksPage
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
    "theme_styles": "transpile",
    "ai_assist": "transpile",
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


# ===========================================================================
# v0.25.1 B7 — Edición iterativa Dashboard preview + regenerate
# ===========================================================================


class PreviewSectionInfo(BaseModel):
    """v0.26.0 — info por sección dentro de una página del preview."""

    type: str
    design_method: str | None = None
    has_ai_image: bool = False
    is_placeholder: bool = False
    asset_id: int | None = None
    headline: str | None = None
    #: v0.27.0 B1 — calidad del asset asociado para badge en /preview.
    asset_quality_score: float | None = None
    asset_quality_flags: list[str] = Field(default_factory=list)
    asset_is_low_quality: bool = False


class PreviewPageInfo(BaseModel):
    """Página vista para el dashboard de preview."""

    slug: str
    title: str
    intent: str | None = None
    n_sections: int = 0
    bricks_page_id: int | None = None
    wp_post_id: int | None = None
    wp_post_status: str | None = None
    last_regenerated_at: datetime | None = None
    #: v0.26.0 B6 — URL R2/local del thumbnail Playwright sobre WP draft.
    preview_thumbnail_url: str | None = None
    preview_captured_at: datetime | None = None
    #: v0.26.0 B7 — secciones (type + design_method) para edición
    #: granular en /preview.
    sections: list[PreviewSectionInfo] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    """GET /preview — info para la UI de revisión iterativa."""

    project_id: int
    project_status: ProjectStatus
    design_method: str | None
    brief: dict[str, Any] | None
    pages: list[PreviewPageInfo]
    #: v0.26.0 B5 — coste agregado de imágenes IA generadas para budget UI.
    image_generation_cost_usd: float = 0.0
    image_generation_budget_usd: float = 1.0


class BriefUpdatePayload(BaseModel):
    """PATCH /brief — campos editables del Brief.

    Solo los campos del business actualizables vía operador. El resto
    del Brief (pages, sections, navigation, footer) se regenera via
    regenerate-page endpoints.
    """

    business_description: str | None = None
    business_sector: str | None = Field(default=None, max_length=80)
    target_audience: str | None = None
    tone_of_voice: str | None = Field(default=None, max_length=20)
    usps_json: list[str] | None = None


class RegeneratePagePayload(BaseModel):
    slug: str = Field(min_length=1, max_length=255)


class RegenerateSectionPayload(BaseModel):
    """v0.26.0 B7 — payload para regenerar UNA sección concreta.

    `design_method` permite cambiar el método solo de esta sección
    (override del marcado en el Brief). Si None, mantiene el existente.
    """

    slug: str = Field(min_length=1, max_length=255)
    section_index: int = Field(ge=0)
    design_method: Literal["templates", "ai"] | None = None


class RegenerateImagePayload(BaseModel):
    """v0.26.0 B7 — payload para regenerar UNA imagen IA en una sección.

    `prompt_override` permite forzar prompt custom; si None, usa el
    prompt heurístico de RedesignImagesAgent.
    """

    slug: str = Field(min_length=1, max_length=255)
    section_index: int = Field(ge=0)
    prompt_override: str | None = Field(default=None, max_length=2000)


@router.get("/{project_id}/preview", response_model=PreviewResponse)
async def get_project_preview(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> PreviewResponse:
    """v0.25.1 B7 — Info de revisión iterativa del proyecto.

    Devuelve el Brief actual + lista de páginas generadas con su
    estado en WP destino. El operador desde `/projects/[id]/preview`
    usa este endpoint para renderizar la pantalla.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    # Cargar bricks_pages del proyecto.
    bp_stmt = select(BricksPage).where(BricksPage.project_id == project_id)
    bp_result = await session.execute(bp_stmt)
    bricks_pages = list(bp_result.scalars())

    # v0.27.0 B1 — cargar Assets del proyecto en bulk para cruzar quality
    # con cada section.asset_id sin N+1.
    assets_stmt = select(Asset).where(Asset.project_id == project_id)
    assets_result = await session.execute(assets_stmt)
    assets_by_id = {a.id: a for a in assets_result.scalars()}

    pages_info: list[PreviewPageInfo] = []
    image_cost_total = 0.0
    # Si tenemos brief, usar como guía de páginas esperadas.
    brief = project.brief_json
    if brief and brief.get("pages"):
        # Map de slug → bricks_page para lookup rápido.
        bp_by_slug = {bp.slug: bp for bp in bricks_pages}
        for brief_page in brief["pages"]:
            slug = brief_page.get("slug") or "/"
            bp = bp_by_slug.get(slug)
            sections_data = brief_page.get("sections") or []
            sections_info = [
                _section_to_preview_info(s, assets_by_id) for s in sections_data
            ]
            for s in sections_data:
                meta = s.get("ai_image_metadata") or {}
                if isinstance(meta, dict):
                    image_cost_total += float(meta.get("cost_usd") or 0)
            pages_info.append(
                PreviewPageInfo(
                    slug=slug,
                    title=brief_page.get("title") or slug,
                    intent=brief_page.get("intent"),
                    n_sections=len(sections_data),
                    bricks_page_id=bp.id if bp else None,
                    wp_post_id=bp.wp_post_id if bp else None,
                    wp_post_status=None,
                    last_regenerated_at=bp.updated_at if bp else None,
                    preview_thumbnail_url=bp.preview_thumbnail_url if bp else None,
                    preview_captured_at=bp.preview_captured_at if bp else None,
                    sections=sections_info,
                )
            )
    else:
        # Sin brief: listar bricks_pages tal cual.
        for bp in bricks_pages:
            pages_info.append(
                PreviewPageInfo(
                    slug=bp.slug,
                    title=bp.title or bp.slug,
                    intent=None,
                    n_sections=len(bp.bricks_json or []),
                    bricks_page_id=bp.id,
                    wp_post_id=bp.wp_post_id,
                    wp_post_status=None,
                    last_regenerated_at=bp.updated_at,
                    preview_thumbnail_url=bp.preview_thumbnail_url,
                    preview_captured_at=bp.preview_captured_at,
                    sections=[],
                )
            )

    budget = float(project.image_generation_budget_usd or 1.0)
    return PreviewResponse(
        project_id=project.id,
        project_status=project.status,
        design_method=project.design_method,
        brief=brief,
        pages=pages_info,
        image_generation_cost_usd=round(image_cost_total, 4),
        image_generation_budget_usd=budget,
    )


def _section_to_preview_info(
    section: dict[str, Any],
    assets_by_id: dict[int, Asset] | None = None,
) -> PreviewSectionInfo:
    """Mapea section del Brief a PreviewSectionInfo plana.

    v0.27.0 — si `assets_by_id` provisto, cruza `asset_id` con quality
    score/flags del Asset para que el dashboard muestre badge "calidad baja".
    """
    asset_id = section.get("asset_id")
    quality_score: float | None = None
    quality_flags: list[str] = []
    is_low_quality = False
    if asset_id and assets_by_id and asset_id in assets_by_id:
        asset = assets_by_id[asset_id]
        if asset.quality_score is not None:
            quality_score = float(asset.quality_score)
            quality_flags = list(asset.quality_flags_json or [])
            is_low_quality = quality_score < 0.50
    return PreviewSectionInfo(
        type=section.get("type", "unknown"),
        design_method=section.get("design_method"),
        has_ai_image=bool(section.get("ai_image_metadata")),
        is_placeholder=False,  # placeholders viven en bricks_json, no en brief
        asset_id=asset_id,
        headline=section.get("headline"),
        asset_quality_score=quality_score,
        asset_quality_flags=quality_flags,
        asset_is_low_quality=is_low_quality,
    )


@router.patch("/{project_id}/brief", response_model=ProjectRead)
async def update_project_brief(
    project_id: int,
    payload: BriefUpdatePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> ProjectRead:
    """v0.25.1 B7 — Editar campos business_* del Brief.

    Actualiza los campos del Project (no toca brief_json directamente).
    Para que los cambios afecten a `brief_json`, el operador debe
    regenerar las páginas afectadas vía `regenerate-page`.

    En MVP solo permite editar business_*. Edición de pages/sections
    del brief queda para v0.25.2.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")

    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(project, key, value)

    # Actualizar brief_json.business con los nuevos valores si existe.
    if project.brief_json and isinstance(project.brief_json, dict):
        business = dict(project.brief_json.get("business") or {})
        if "business_description" in data:
            business["description"] = data["business_description"]
        if "business_sector" in data:
            business["sector"] = data["business_sector"]
        if "target_audience" in data:
            business["target_audience"] = data["target_audience"]
        if "tone_of_voice" in data:
            business["tone_of_voice"] = data["tone_of_voice"]
        if "usps_json" in data:
            business["usps"] = data["usps_json"]
        project.brief_json = {**project.brief_json, "business": business}

    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.post(
    "/{project_id}/preview/regenerate-page",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_preview_page(
    project_id: int,
    payload: RegeneratePagePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.25.1 B7 — Encola Celery task que re-ejecuta el agente de
    rediseño SOLO para una página (filtrada del Brief).

    Útil tras editar el Brief con `PATCH /brief` (regenerar páginas
    afectadas) o si la calidad de la página no satisface al operador
    (re-tirada para variar la generación AI/templates).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    # v0.26.0 — acepta también Hybrid (design_method=None) además de
    # templates/ai puros.
    if not project.brief_json or not project.brief_json.get("pages"):
        raise ConflictError(
            "Project sin brief_json. BriefGenerator no corrió o "
            "el brief está vacío."
        )

    task_id = enqueue_preview_regenerate_page(project_id, payload.slug)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "slug": payload.slug,
        "design_method": project.design_method,
    }


@router.post(
    "/{project_id}/preview/regenerate-section",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_preview_section(
    project_id: int,
    payload: RegenerateSectionPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.26.0 B7 — Regenerar UNA sección concreta de una página.

    Si `payload.design_method` está presente, actualiza el campo del
    Brief para que el siguiente run use ese método. Luego encola la
    misma task que regenerate-page (que filtra por slug y aplica
    Templates/AI según el design_method actualizado).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    brief = project.brief_json
    if not brief or not brief.get("pages"):
        raise ConflictError("Project sin brief_json.")

    page = next(
        (p for p in brief["pages"] if p.get("slug") == payload.slug), None
    )
    if page is None:
        raise NotFoundError(f"Página '{payload.slug}' no encontrada en el brief.")
    sections = page.get("sections") or []
    if payload.section_index >= len(sections):
        raise NotFoundError(
            f"section_index={payload.section_index} fuera de rango "
            f"(página tiene {len(sections)} secciones)."
        )

    # Override del design_method de la sección si payload lo trae.
    if payload.design_method is not None:
        sections[payload.section_index]["design_method"] = payload.design_method
        # Marca brief_json modificado para que SQLAlchemy persista el cambio.
        project.brief_json = dict(brief)  # shallow copy to trigger update

    await session.commit()

    task_id = enqueue_preview_regenerate_page(project_id, payload.slug)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "slug": payload.slug,
        "section_index": payload.section_index,
        "design_method_applied": (
            payload.design_method
            or sections[payload.section_index].get("design_method")
        ),
    }


@router.post(
    "/{project_id}/preview/regenerate-image",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_preview_image(
    project_id: int,
    payload: RegenerateImagePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.26.0 B7 — Regenerar imagen IA de UNA sección concreta.

    Vacía el `asset_id` y `ai_image_metadata` de la sección en el Brief
    para que RedesignImagesAgent la trate como slot vacío de nuevo, y
    encola la task del preview que invoca al agente para esa página.
    Si `prompt_override` está presente, se persiste en `ai_image_prompt_override`
    de la sección y el agente lo respetará en su próximo run.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    brief = project.brief_json
    if not brief or not brief.get("pages"):
        raise ConflictError("Project sin brief_json.")

    page = next(
        (p for p in brief["pages"] if p.get("slug") == payload.slug), None
    )
    if page is None:
        raise NotFoundError(f"Página '{payload.slug}' no encontrada en el brief.")
    sections = page.get("sections") or []
    if payload.section_index >= len(sections):
        raise NotFoundError(
            f"section_index={payload.section_index} fuera de rango."
        )

    section = sections[payload.section_index]
    section.pop("asset_id", None)
    section.pop("image_url", None)
    section.pop("ai_image_metadata", None)
    if payload.prompt_override is not None:
        section["ai_image_prompt_override"] = payload.prompt_override
    else:
        section.pop("ai_image_prompt_override", None)
    project.brief_json = dict(brief)  # trigger SQLAlchemy update

    await session.commit()

    task_id = enqueue_preview_regenerate_page(project_id, payload.slug)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "slug": payload.slug,
        "section_index": payload.section_index,
    }


# ============================================================================
# v0.27.0 B4 — Brief refinement endpoints
# ============================================================================


class BriefRefinementProposal(BaseModel):
    """Una propuesta individual generada por gpt-5.5."""

    id: str
    category: Literal["copy", "cta", "design_method", "reorder"]
    page_slug: str
    section_index: int
    before: dict[str, Any]
    after: dict[str, Any]
    rationale: str
    impact_estimate: Literal["low", "medium", "high"]
    applied_at: datetime | None = None


class BriefRefinementsResponse(BaseModel):
    """GET /brief/refinements — batch persistido o vacío."""

    project_id: int
    generated_at: datetime | None = None
    model: str | None = None
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    proposals: list[BriefRefinementProposal] = Field(default_factory=list)


class ApplyRefinementPayload(BaseModel):
    """POST /brief/apply-refinement payload."""

    proposal_id: str = Field(min_length=1, max_length=64)
    regenerate: bool = Field(
        default=False,
        description="Si True, encola wcm.preview.regenerate_page tras aplicar.",
    )


def _apply_refinement_to_brief(
    brief: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    """v0.27.0 — aplica una propuesta al Brief (in-place mutation OK).

    Devuelve el Brief modificado. Lanza `ValueError` si la propuesta
    es inválida (page_slug no existe, section_index fuera de rango,
    category desconocida).
    """
    category = proposal["category"]
    page_slug = proposal["page_slug"]
    section_index = int(proposal["section_index"])
    after = proposal.get("after") or {}

    page = next(
        (p for p in brief.get("pages", []) if p.get("slug") == page_slug),
        None,
    )
    if page is None:
        raise ValueError(f"page_slug={page_slug!r} no encontrado en el Brief")
    sections = page.get("sections") or []

    if category == "reorder":
        new_order = after.get("new_order") or []
        if not isinstance(new_order, list) or len(new_order) != len(sections):
            raise ValueError(
                f"reorder new_order debe ser lista de {len(sections)} índices "
                f"distintos; recibido {new_order!r}"
            )
        if sorted(new_order) != list(range(len(sections))):
            raise ValueError(
                f"reorder new_order debe ser permutación de 0..{len(sections)-1}"
            )
        page["sections"] = [sections[i] for i in new_order]
        return brief

    # copy/cta/design_method: necesitan section_index válido.
    if section_index >= len(sections):
        raise ValueError(
            f"section_index={section_index} fuera de rango "
            f"(página tiene {len(sections)} secciones)"
        )
    section = sections[section_index]

    if category == "copy":
        key = after.get("key")
        value = after.get("value")
        if key not in ("headline", "subheadline", "text", "description"):
            raise ValueError(
                f"copy key inválido: {key!r}. Permitidos: "
                "headline/subheadline/text/description."
            )
        section[key] = value
    elif category == "cta":
        if "cta_text" in after:
            section["cta_text"] = after["cta_text"]
        if "cta_url" in after:
            section["cta_url"] = after["cta_url"]
    elif category == "design_method":
        new_method = after.get("design_method")
        if new_method not in ("templates", "ai"):
            raise ValueError(
                f"design_method inválido: {new_method!r}. Permitidos: templates/ai."
            )
        section["design_method"] = new_method
    else:
        raise ValueError(f"category desconocida: {category!r}")

    return brief


@router.post(
    "/{project_id}/brief/suggest-refinements",
    status_code=status.HTTP_202_ACCEPTED,
)
async def suggest_brief_refinements(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.27.0 B4 — Encola BriefRefinementAgent que propone mejoras al
    Brief con AI. Resultado persistido en
    `Project.brief_refinement_proposals_json` y consumido por
    `GET /brief/refinements`.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if not project.brief_json or not project.brief_json.get("pages"):
        raise ConflictError(
            "Project sin brief_json. BriefGenerator debe correr antes."
        )

    task_id = enqueue_brief_suggest_refinements(project_id)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "status": "queued",
    }


@router.get(
    "/{project_id}/brief/refinements",
    response_model=BriefRefinementsResponse,
)
async def get_brief_refinements(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> BriefRefinementsResponse:
    """v0.27.0 B4 — Devuelve la última batch de propuestas persistida."""
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    data = project.brief_refinement_proposals_json or {}
    return BriefRefinementsResponse(
        project_id=project_id,
        generated_at=data.get("generated_at"),
        model=data.get("model"),
        cost_usd=float(data.get("cost_usd") or 0),
        tokens_in=int(data.get("tokens_in") or 0),
        tokens_out=int(data.get("tokens_out") or 0),
        proposals=[
            BriefRefinementProposal.model_validate(p)
            for p in (data.get("proposals") or [])
        ],
    )


@router.post(
    "/{project_id}/brief/apply-refinement",
    status_code=status.HTTP_202_ACCEPTED,
)
async def apply_brief_refinement(
    project_id: int,
    payload: ApplyRefinementPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.27.0 B4 — Aplica UNA propuesta concreta al Brief.

    Idempotente: si `proposal.applied_at` ya está seteado, no re-aplica
    pero sí encola regenerate si `regenerate=true`.

    Si `regenerate=True`, encola `wcm.preview.regenerate_page` para la
    página afectada tras editar el Brief.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if not project.brief_json:
        raise ConflictError("Project sin brief_json.")
    refinements = project.brief_refinement_proposals_json or {}
    proposals_list = refinements.get("proposals") or []
    proposal = next(
        (p for p in proposals_list if p.get("id") == payload.proposal_id),
        None,
    )
    if proposal is None:
        raise NotFoundError(
            f"proposal_id={payload.proposal_id!r} no encontrado en el batch actual."
        )

    already_applied = bool(proposal.get("applied_at"))
    page_slug = proposal["page_slug"]

    if not already_applied:
        # Aplicar al Brief.
        try:
            new_brief = _apply_refinement_to_brief(
                dict(project.brief_json), proposal,
            )
        except ValueError as e:
            raise ConflictError(f"propuesta inválida: {e}") from e
        project.brief_json = new_brief
        proposal["applied_at"] = datetime.now(UTC).isoformat()
        # Re-asignar el dict para que SQLAlchemy persista el cambio del JSONB.
        project.brief_refinement_proposals_json = {
            **refinements, "proposals": proposals_list,
        }

    await session.commit()

    task_id = None
    if payload.regenerate:
        task_id = enqueue_preview_regenerate_page(project_id, page_slug)

    return {
        "project_id": project_id,
        "proposal_id": payload.proposal_id,
        "already_applied": already_applied,
        "regenerate_task_id": task_id,
        "regenerated": payload.regenerate,
    }


@router.post(
    "/{project_id}/preview/approve",
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve_preview(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """v0.25.1 B7 — Aprobar preview y publicar.

    Cambia project.status → COMPLETED y encola PublishAgent que pasa
    todas las páginas draft → publish en WP destino.

    Es esencialmente un alias de `POST /publish` con marca de
    `status=COMPLETED` previa (semánticamente: 'el operador validó
    el preview y aprueba el deploy').
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if project.status not in (
        ProjectStatus.READY_FOR_PREVIEW,
        ProjectStatus.COMPLETED,
        ProjectStatus.QA_FAILED,
    ):
        raise ConflictError(
            f"approve solo válido en status ready_for_preview/completed/qa_failed. "
            f"Estado actual: {project.status.value}."
        )
    project.status = ProjectStatus.COMPLETED
    await session.commit()
    task_id = enqueue_project_publish(project_id)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "status": "approved_publishing",
    }

