"""CRUD del singleton `email_layouts` (v0.14.0).

Una sola fila editable (`id=1`, forzado por CHECK constraint) con la
shell HTML maestra de los correos de outreach. El composer la inyecta
al renderizar cada step.

RBAC:
- GET: any_user (operadores pueden ver el layout actual y hacer preview).
- PUT: admin only — cambiar la shell afecta a TODOS los correos
  futuros del producto.

Cualquier `PUT` deja AuditLog con action `EMAIL_LAYOUT_UPDATE` y
persiste el `updated_by_user_id` en la propia fila para trazabilidad
rápida desde la UI sin abrir la timeline.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jinja2 import Environment, TemplateSyntaxError
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import NotFoundError
from wcm_api.security import TokenPayload, get_current_user_payload, require_role
from wcm_db.models.audit import AuditLog
from wcm_db.models.outreach import EmailLayout
from wcm_types.enums import AuditAction, UserRole
from wcm_types.schemas.outreach import EmailLayoutRead, EmailLayoutUpdate

router = APIRouter(prefix="/email-layout", tags=["email-layout"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_admin_only = require_role(UserRole.ADMIN.value)


@router.get("", response_model=EmailLayoutRead)
async def get_email_layout(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> EmailLayoutRead:
    """Devuelve el singleton id=1. Si la tabla está vacía (migración no
    aplicada todavía en este entorno) retorna 404 — el cliente debe
    aplicar la migración antes de editar.
    """
    layout = await session.get(EmailLayout, 1)
    if layout is None:
        raise NotFoundError(
            "Email layout no inicializado. Aplica la migración 0005 "
            "(`alembic upgrade head`) para crear el singleton."
        )
    return EmailLayoutRead.model_validate(layout)


@router.put("", response_model=EmailLayoutRead)
async def put_email_layout(
    payload: EmailLayoutUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_admin_only)],
) -> EmailLayoutRead:
    """Reemplaza completo el layout HTML + CSS. Valida sintaxis Jinja2
    antes de persistir (si está rota → 422 antes de tocar BD).

    El composer reusará automáticamente esta versión en próximos drafts.
    Sequences ya generadas conservan su snapshot HTML en
    `outreach_sends.body_html_rendered` — los cambios NO son retroactivos.
    """
    # Validación sintáctica del Jinja2 — más rápida y específica que
    # esperar a que el composer falle al renderizar el primer correo.
    try:
        Environment().parse(payload.layout_html)
    except TemplateSyntaxError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sintaxis Jinja2 inválida en layout_html: {e.message} (línea {e.lineno})",
        ) from e

    layout = await session.get(EmailLayout, 1)
    if layout is None:
        # Defensa: si la migración no se aplicó, crear el singleton aquí.
        layout = EmailLayout(
            id=1,
            layout_html=payload.layout_html,
            layout_css=payload.layout_css,
            updated_by_user_id=int(user.sub) if user.sub.isdigit() else None,
        )
        session.add(layout)
    else:
        layout.layout_html = payload.layout_html
        layout.layout_css = payload.layout_css
        layout.updated_by_user_id = int(user.sub) if user.sub.isdigit() else None

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.EMAIL_LAYOUT_UPDATE,
            entity_type="email_layout",
            entity_id="1",
            legal_ground=None,
            payload={
                "html_chars": len(payload.layout_html),
                "css_chars": len(payload.layout_css),
                "operator_role": user.role,
            },
        )
    )
    await session.commit()
    await session.refresh(layout)
    return EmailLayoutRead.model_validate(layout)
