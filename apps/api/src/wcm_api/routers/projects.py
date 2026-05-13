"""Endpoints de proyectos de migración + fases.

Operaciones expuestas:
- list / get / create / update
- start (lanza el pipeline en worker)
- resume (reanuda tras error)
- cancel (marca cancelado, NO interrumpe job en vuelo, eso es Fase 6)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wcm_db.models.projects import Project, ProjectPhase
from wcm_types.enums import ProjectStatus, UserRole
from wcm_types.schemas.projects import (
    ProjectCreate,
    ProjectPhaseRead,
    ProjectRead,
    ProjectUpdate,
)

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.security import require_role
from wcm_api.tasks.enqueue import enqueue_project_pipeline

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
    project.started_at = datetime.now(timezone.utc)
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
