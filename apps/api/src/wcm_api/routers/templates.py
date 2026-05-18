"""CRUD de plantillas de contacto (Jinja2 en BD).

Migradas de ficheros `.j2` en disco a tabla `outreach_templates` en
v0.12.0. El composer las resuelve por `name` (string opaco que sigue
viviendo en `OutreachSequence.template_name` como referencia
histórica).

RBAC:
- LECTURA (`GET`): any_user (operadores leen para preview).
- ESCRITURA (`POST/PATCH/DELETE`): admin only — un cambio de
  plantilla afecta a TODOS los drafts futuros del producto.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.security import require_role
from wcm_db.models.outreach import OutreachTemplate
from wcm_types.enums import UserRole
from wcm_types.schemas.outreach import (
    OutreachTemplateCreate,
    OutreachTemplateRead,
    OutreachTemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])

_any_user = require_role(
    UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value
)
_admin_only = require_role(UserRole.ADMIN.value)


@router.get("", response_model=list[OutreachTemplateRead])
async def list_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    language: str | None = Query(default=None, min_length=2, max_length=8),
) -> list[OutreachTemplateRead]:
    stmt = select(OutreachTemplate).order_by(OutreachTemplate.name)
    if language:
        stmt = stmt.where(OutreachTemplate.language == language)
    rows = (await session.execute(stmt)).scalars().all()
    return [OutreachTemplateRead.model_validate(t) for t in rows]


@router.get("/{template_id}", response_model=OutreachTemplateRead)
async def get_template(
    template_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> OutreachTemplateRead:
    t = await session.get(OutreachTemplate, template_id)
    if t is None:
        raise NotFoundError(f"Template {template_id} no encontrado")
    return OutreachTemplateRead.model_validate(t)


@router.post(
    "",
    response_model=OutreachTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    payload: OutreachTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> OutreachTemplateRead:
    t = OutreachTemplate(
        name=payload.name,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        language=payload.language,
    )
    session.add(t)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise ConflictError(
            f"Ya existe una plantilla con nombre {payload.name!r}",
        ) from e
    await session.refresh(t)
    return OutreachTemplateRead.model_validate(t)


@router.patch("/{template_id}", response_model=OutreachTemplateRead)
async def update_template(
    template_id: int,
    payload: OutreachTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> OutreachTemplateRead:
    """Actualiza subject/body/language de una plantilla. NO se permite
    cambiar `name` — es la clave por la que el composer resuelve;
    renombrar rompería sequences históricas que la referencian.
    """
    t = await session.get(OutreachTemplate, template_id)
    if t is None:
        raise NotFoundError(f"Template {template_id} no encontrado")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(t, k, v)
    await session.commit()
    await session.refresh(t)
    return OutreachTemplateRead.model_validate(t)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_only)],
) -> None:
    """Borra una plantilla. Las sequences históricas guardan
    `template_name` como string opaco, así que borrar la plantilla NO
    rompe sequences ya generadas — solo afecta a drafts futuros que
    pidan esa plantilla por nombre (caerán al fallback `.j2` si existe,
    o fallarán al componer).
    """
    t = await session.get(OutreachTemplate, template_id)
    if t is None:
        raise NotFoundError(f"Template {template_id} no encontrado")
    await session.delete(t)
    await session.commit()
