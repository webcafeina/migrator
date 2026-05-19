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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jinja2 import Environment, TemplateSyntaxError
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.email_layout_renderer import generate_layout_from_theme
from wcm_api.errors import NotFoundError
from wcm_api.rate_limit import limiter
from wcm_api.security import TokenPayload, get_current_user_payload, require_role
from wcm_db.models.audit import AuditLog
from wcm_db.models.outreach import EmailLayout
from wcm_types.enums import AuditAction, UserRole
from wcm_types.schemas.outreach import (
    EmailLayoutRead,
    EmailLayoutTheme,
    EmailLayoutUpdate,
)

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
    """Reemplaza el layout. v0.15.0 acepta 3 modos:

    1. `theme_config` poblado → backend regenera `layout_html` y
       `layout_css` desde la plantilla canónica + persiste el tema.
    2. `layout_html` + `layout_css` sin tema y `clear_theme=true` →
       persiste HTML/CSS tal cual y BORRA el tema (modo Código).
    3. `layout_html` + `layout_css` sin tema y sin `clear_theme` →
       mismo que (2). Conservado para compat retro.

    Sequences ya generadas conservan su snapshot HTML en
    `outreach_sends.body_html_rendered` — los cambios NO son retroactivos.
    """
    # Determinar modo y validar.
    final_html: str
    final_css: str
    final_theme: EmailLayoutTheme | None

    if payload.theme_config is not None:
        # Modo Visual: backend regenera. El theme ya viene validado
        # por pydantic (HEX patterns + bounds numéricos).
        final_html, final_css = generate_layout_from_theme(payload.theme_config)
        final_theme = payload.theme_config
    else:
        # Modo Código: el cliente manda HTML+CSS crudos.
        if payload.layout_html is None or not payload.layout_html.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Falta `theme_config` o `layout_html` con contenido.",
            )
        # Validación sintáctica del Jinja2 — más rápida y específica
        # que esperar a que el composer falle al renderizar el primer
        # correo.
        try:
            Environment().parse(payload.layout_html)
        except TemplateSyntaxError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Sintaxis Jinja2 inválida en layout_html: {e.message} (línea {e.lineno})",
            ) from e
        final_html = payload.layout_html
        final_css = payload.layout_css if payload.layout_css is not None else ""
        final_theme = None  # tab Código → tema desactivado

    layout = await session.get(EmailLayout, 1)
    # `user.sub` es el UUID del usuario como string. Lo casteamos a UUID
    # (silencioso si por algún motivo no es válido — el endpoint sigue
    # funcionando aunque la trazabilidad inline se pierda; AuditLog
    # captura siempre el actor).
    try:
        user_uuid: UUID | None = UUID(user.sub)
    except (ValueError, AttributeError):
        user_uuid = None

    theme_jsonable = final_theme.model_dump(mode="json") if final_theme is not None else None

    if layout is None:
        # Defensa: si la migración no se aplicó, crear el singleton aquí.
        layout = EmailLayout(
            id=1,
            layout_html=final_html,
            layout_css=final_css,
            theme_config=theme_jsonable,
            updated_by_user_id=user_uuid,
        )
        session.add(layout)
    else:
        layout.layout_html = final_html
        layout.layout_css = final_css
        layout.theme_config = theme_jsonable
        layout.updated_by_user_id = user_uuid

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.EMAIL_LAYOUT_UPDATE,
            entity_type="email_layout",
            entity_id="1",
            legal_ground=None,
            payload={
                "mode": "visual" if final_theme is not None else "code",
                "html_chars": len(final_html),
                "css_chars": len(final_css),
                "operator_role": user.role,
            },
        )
    )
    await session.commit()
    await session.refresh(layout)
    return EmailLayoutRead.model_validate(layout)


@router.post("/preview", response_model=dict)
@limiter.limit("60/minute")
async def preview_email_layout(
    request: Request,
    theme: EmailLayoutTheme,
    _: Annotated[object, Depends(_admin_only)],
) -> dict:
    """Genera HTML+CSS desde un tema SIN persistir. Útil para el
    LivePreview del form Visual con debounce — cada cambio dispara
    este endpoint y el iframe se actualiza con el resultado.

    Rate-limited a 60/min por IP para evitar abuso si el operador
    arrastra un color picker rápido. El frontend debería cancelar
    requests anteriores con AbortController.
    """
    html, css = generate_layout_from_theme(theme)
    return {"layout_html": html, "layout_css": css}
