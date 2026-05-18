"""Lectura y actualización de tareas residuales (entregable humano).

Los `residual_tasks` los crean los subagentes durante el pipeline.
Aquí solo se exponen para que el dashboard los muestre y permita
marcarlos como done (que dispara sync a ClickUp).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import NotFoundError
from wcm_api.security import require_role
from wcm_api.tasks.enqueue import enqueue_residual_sync_clickup
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import ResidualCategory, ResidualStatus, UserRole
from wcm_types.schemas.residual_tasks import ResidualTaskRead

router = APIRouter(prefix="/residual-tasks", tags=["residual-tasks"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


class UpdateStatusPayload(BaseModel):
    status: ResidualStatus


@router.get("", response_model=list[ResidualTaskRead])
async def list_residual_tasks(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    project_id: int | None = None,
    category: ResidualCategory | None = None,
    status_filter: ResidualStatus | None = None,
) -> list[ResidualTaskRead]:
    stmt = select(ResidualTask).order_by(ResidualTask.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(ResidualTask.project_id == project_id)
    if category is not None:
        stmt = stmt.where(ResidualTask.category == category)
    if status_filter is not None:
        stmt = stmt.where(ResidualTask.status == status_filter)
    items = (await session.execute(stmt)).scalars().all()
    return [ResidualTaskRead.model_validate(t) for t in items]


class ResidualTaskStats(BaseModel):
    """Agregados de tareas residuales para el topbar de
    `/residual-tasks`. Counts por status + por categoría +
    estimación de tiempo pendiente.
    """

    total: int
    open: int = Field(description="Status OPEN (sin tocar).")
    in_progress: int
    blocked: int
    done: int
    skipped: int

    blocking_go_live: int = Field(
        description="Tareas de la categoría más urgente, agnóstico al status."
    )
    distinct_projects: int
    estimated_minutes_pending: int = Field(
        description="Suma de estimated_minutes de tareas no DONE/SKIPPED."
    )


@router.get("/stats", response_model=ResidualTaskStats)
async def residual_task_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> ResidualTaskStats:
    """Agregados globales de tareas residuales para el topbar.

    `estimated_minutes_pending` da una cifra accionable: "te quedan X
    minutos de trabajo manual repartido". Excluye DONE/SKIPPED para
    que solo cuente lo realmente pendiente.
    """
    total = (
        await session.execute(select(func.count()).select_from(ResidualTask))
    ).scalar_one()

    async def count_by_status(s: ResidualStatus) -> int:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ResidualTask)
                    .where(ResidualTask.status == s)
                )
            ).scalar_one()
        )

    open_n = await count_by_status(ResidualStatus.OPEN)
    in_progress = await count_by_status(ResidualStatus.IN_PROGRESS)
    blocked = await count_by_status(ResidualStatus.BLOCKED)
    done = await count_by_status(ResidualStatus.DONE)
    skipped = await count_by_status(ResidualStatus.SKIPPED)

    blocking_go_live = (
        await session.execute(
            select(func.count())
            .select_from(ResidualTask)
            .where(ResidualTask.category == ResidualCategory.BLOCKING_GO_LIVE)
        )
    ).scalar_one()
    distinct_projects = (
        await session.execute(
            select(func.count(func.distinct(ResidualTask.project_id)))
        )
    ).scalar_one()
    estimated_minutes_pending = (
        await session.execute(
            select(func.coalesce(func.sum(ResidualTask.estimated_minutes), 0)).where(
                ResidualTask.status.notin_(
                    [ResidualStatus.DONE, ResidualStatus.SKIPPED]
                )
            )
        )
    ).scalar_one()

    return ResidualTaskStats(
        total=int(total),
        open=open_n,
        in_progress=in_progress,
        blocked=blocked,
        done=done,
        skipped=skipped,
        blocking_go_live=int(blocking_go_live),
        distinct_projects=int(distinct_projects),
        estimated_minutes_pending=int(estimated_minutes_pending),
    )


@router.patch("/{task_id}/status", response_model=ResidualTaskRead)
async def update_residual_status(
    task_id: int,
    payload: UpdateStatusPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> ResidualTaskRead:
    task = await session.get(ResidualTask, task_id)
    if task is None:
        raise NotFoundError(f"ResidualTask {task_id} no encontrado")
    task.status = payload.status
    if payload.status == ResidualStatus.DONE:
        task.closed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(task)
    # Encolar sync con ClickUp (Fase 10 lo implementará realmente)
    enqueue_residual_sync_clickup(task.project_id)
    return ResidualTaskRead.model_validate(task)
