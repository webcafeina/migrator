"""Endpoints de proyectos de migración + fases.

Operaciones expuestas:
- list / get / create / update
- start (lanza el pipeline en worker)
- resume (reanuda tras error)
- cancel (marca cancelado, NO interrumpe job en vuelo, eso es Fase 6)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.security import require_role
from wcm_api.tasks.enqueue import enqueue_project_pipeline
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
    ProjectCreate,
    ProjectPhaseRead,
    ProjectRead,
    ProjectUpdate,
)
from wcm_types.schemas.qa_reports import QaReportRead
from wcm_types.schemas.visual_diffs import (
    VisualDiffRead,
    VisualDiffsListResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


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
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    if project.status == ProjectStatus.RUNNING:
        raise ConflictError(f"Project {project_id} ya está en ejecución")
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
) -> dict:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} no encontrado")
    project.status = ProjectStatus.RUNNING
    await session.commit()
    task_id = enqueue_project_pipeline(project_id, resume=True)
    return {"task_id": task_id, "status": "queued", "project_id": project_id, "resume": True}


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
