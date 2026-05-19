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

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.rate_limit import limiter
from wcm_api.security import require_role
from wcm_db.models.outreach import OutreachTemplate
from wcm_types.enums import UserRole
from wcm_types.schemas.outreach import (
    OutreachPreviewResponse,
    OutreachTemplateBase,
    OutreachTemplateCreate,
    OutreachTemplateRead,
    OutreachTemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
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
        body_html_template=payload.body_html_template,
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
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
    """Actualiza campos de una plantilla. NO se permite cambiar `name`
    — es la clave por la que el composer resuelve; renombrar rompería
    sequences históricas que la referencian.

    v0.14.0 — usamos `exclude_unset=True` (no `exclude_none=True`) para
    distinguir entre:
    - campo no enviado por el cliente → no tocar;
    - campo enviado como `None` → vaciar explícitamente (útil para
      retirar el `body_html_template` de una plantilla y que vuelva
      al fallback de texto).
    """
    t = await session.get(OutreachTemplate, template_id)
    if t is None:
        raise NotFoundError(f"Template {template_id} no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(t, k, v)
    await session.commit()
    await session.refresh(t)
    return OutreachTemplateRead.model_validate(t)


@router.get("/{template_id}/preview", response_model=OutreachPreviewResponse)
async def preview_template(
    template_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> OutreachPreviewResponse:
    """Renderiza la plantilla con un contexto mockeado (lead demo) +
    layout maestro + premailer. Útil para que el operador vea cómo
    quedará el correo desde `/settings/templates` antes de aprobarla.

    El HTML retornado YA tiene CSS inlined — el cliente lo pinta en un
    iframe `srcDoc` sin más procesamiento.
    """
    t = await session.get(OutreachTemplate, template_id)
    if t is None:
        raise NotFoundError(f"Template {template_id} no encontrado")
    html, subject = await _render_template_with_mock_context(t, session)
    return OutreachPreviewResponse(html=html, subject=subject)


async def _render_template_with_mock_context(
    t: OutreachTemplate,
    session: AsyncSession,
) -> tuple[str, str]:
    """Helper privado: genera el HTML completo de una plantilla con
    datos de un lead demo + settings de empresa. Usado por el endpoint
    preview de plantilla.

    Importamos lazy de wcm_worker para no acoplar el bootstrap del API
    al worker en imports module-level (mismo patrón que health.py:127
    y outreach.py:205).
    """
    import os

    from jinja2 import Environment, StrictUndefined, select_autoescape

    from wcm_db.models.outreach import EmailLayout
    from wcm_worker.integrations.email_layout import (
        EmailLayoutSnapshot,
        load_layout,
        render_full_email,
    )
    from wcm_worker.integrations.html_email import is_html, wrap_plain_as_html

    env = Environment(
        autoescape=select_autoescape(default=False, default_for_string=False),
        undefined=StrictUndefined,
    )
    mock_ctx = {
        # Demo realista para que el operador entienda cómo queda con
        # contenido real, no con placeholders crípticos.
        "business_name": "Restaurante Demo",
        "website_url": "https://restaurantedemo.es",
        "builder_label": "Wix",
        "sender_name": "Equipo Webcafeína",
        "company_name": os.environ.get("COMPANY_LEGAL_NAME", "Webcafeína S.L."),
        "company_city": "Cáceres",
        "company_legal_name": os.environ.get("COMPANY_LEGAL_NAME", "Webcafeína S.L."),
        "company_cif": os.environ.get("COMPANY_CIF", "B10463990"),
        "company_address": os.environ.get(
            "COMPANY_ADDRESS",
            "Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres",
        ),
        "company_contact_email": os.environ.get("COMPANY_CONTACT_EMAIL", "info@webcafeina.com"),
        "privacy_policy_url": os.environ.get(
            "COMPANY_PRIVACY_POLICY_URL",
            "https://webcafeina.com/politica-de-privacidad",
        ),
        "opt_out_url": "https://migrator.webcafeina.com/opt-out?token=PREVIEW",
        "legal_block": (
            f"{os.environ.get('COMPANY_LEGAL_NAME', 'Webcafeína S.L.')} · "
            "Tratamiento de datos al amparo del art. 6.1.f RGPD."
        ),
        "previous_subject": "vuestra web",
        "logo_url": os.environ.get("EMAIL_LOGO_URL", "") or "",
    }
    subject_tpl = env.from_string(t.subject_template)
    subject = subject_tpl.render(**mock_ctx).strip()

    if t.body_html_template:
        body_html_content = env.from_string(t.body_html_template).render(**mock_ctx)
    else:
        body_html_content = wrap_plain_as_html(env.from_string(t.body_template).render(**mock_ctx))
    if not is_html(body_html_content):
        body_html_content = wrap_plain_as_html(body_html_content)

    # `load_layout` espera Session sync. Aquí leemos el singleton con
    # la sesión async del API y construimos el EmailLayoutSnapshot a
    # mano para que el operador vea el preview con el layout REAL que
    # tenga en BD (no el fallback hardcoded).
    layout_row = await session.get(EmailLayout, 1)
    if layout_row is None:
        layout = load_layout(None)  # → fallback hardcoded
    else:
        layout = EmailLayoutSnapshot(
            layout_html=layout_row.layout_html,
            layout_css=layout_row.layout_css,
        )
    html = render_full_email(
        layout,
        content_html=body_html_content,
        subject=subject,
        cta_label=t.cta_label,
        cta_url=t.cta_url,
        logo_url=mock_ctx["logo_url"],
        template_ctx=mock_ctx,
    )
    return html, subject


@router.post("/preview", response_model=OutreachPreviewResponse)
@limiter.limit("60/minute")
async def preview_inline_template(
    request: Request,
    payload: OutreachTemplateBase,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> OutreachPreviewResponse:
    """Renderiza un payload de plantilla SIN persistirla. v0.15.0 —
    alimenta el preview lateral del `TemplateForm` con debounce 600 ms
    para que el operador vea cambios en vivo mientras edita.

    Reutiliza `_render_template_with_mock_context` construyendo una
    instancia transitoria de `OutreachTemplate` (no se añade a la
    sesión, no toca BD). Rate-limit 60/min por IP.
    """
    transient = OutreachTemplate(
        name=payload.name,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        language=payload.language,
        body_html_template=payload.body_html_template,
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
    )
    html, subject = await _render_template_with_mock_context(transient, session)
    return OutreachPreviewResponse(html=html, subject=subject)


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
