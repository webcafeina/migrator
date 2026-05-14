"""Opt-out RGPD (público).

Endpoint que el receptor del outreach abre desde el link del email. Token
firmado JWT con `purpose=opt_out`. Tras validar, elimina el lead (cascade
borra enriquecimientos + secuencias) y registra el opt-out permanentemente
en `opt_out_log` para evitar recontacto futuro.

NO requiere auth de operador. La autenticación es el token firmado, lo que
demuestra que el solicitante recibió legítimamente el email.

Está fuera del prefijo `/api/v1` porque es un endpoint humano-facing:
los receptores ven una URL `https://migrator.webcafeina.com/opt-out?token=...`
y esperan respuesta HTML, no JSON.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.config import ApiSettings, get_settings
from wcm_api.db import get_session
from wcm_api.security import decode_opt_out_token
from wcm_db.models.leads import Lead, OptOutLog
from wcm_types.enums import LeadStatus

router = APIRouter(tags=["opt-out"])


_CONFIRMATION_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Baja registrada — Webcafeína</title>
  <style>
    body {{
      background: #171009; color: #F2E8D2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0; padding: 48px 24px;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: #2B1A0E; max-width: 560px; padding: 40px;
      border-radius: 12px; border: 1px solid #5A3519;
    }}
    h1 {{ color: #B1F100; margin: 0 0 16px; font-size: 24px; }}
    p {{ line-height: 1.6; }}
    .meta {{ color: #5A3519; font-size: 13px; margin-top: 32px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Baja registrada</h1>
    <p>Has sido eliminado de nuestra base de contactos. No volverás a
       recibir comunicaciones comerciales de Webcafeína.</p>
    <p>Si has llegado aquí por error o no recuerdas haber recibido un
       mensaje nuestro, puedes contactarnos en
       <a href="mailto:{contact}" style="color:#B1F100">{contact}</a>.</p>
    <p class="meta">Webcafeína S.L. — derecho de oposición ejercido al
       amparo del art. 21 RGPD. Tratamiento de datos:
       <a href="{privacy}" style="color:#B1F100">política de privacidad</a>.</p>
  </div>
</body>
</html>"""


@router.get("/opt-out", response_class=HTMLResponse)
async def opt_out_get(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
    token: str = Query(..., min_length=10),
) -> HTMLResponse:
    """Procesa el opt-out: valida token, borra lead, registra en opt_out_log,
    y devuelve la página HTML de confirmación.

    Idempotente: si el lead ya está borrado y el opt-out ya registrado, sigue
    devolviendo 200 con el HTML — el receptor no debe ver error.
    """
    payload = decode_opt_out_token(token, settings=settings)
    email = payload["email"]
    lead_id = payload.get("lead_id")

    # 1) Registrar en opt_out_log (idempotente por unique constraint
    #    email+channel). Si ya existe, ignorar el error.
    existing_optout = (
        await session.execute(
            select(OptOutLog).where(
                OptOutLog.email == email, OptOutLog.channel == "email"
            )
        )
    ).scalar_one_or_none()

    if existing_optout is None:
        session.add(
            OptOutLog(
                email=email,
                lead_id_at_optout=lead_id,
                channel="email",
                evidence=f"token_jti={payload.get('jti')}",
            )
        )

    # 2) Buscar y eliminar lead (cascade limpia enrichments + sequences)
    if lead_id is not None:
        lead = await session.get(Lead, lead_id)
        if lead is not None:
            lead.status = LeadStatus.OPTED_OUT  # último estado antes del delete
            await session.delete(lead)
    else:
        # Fallback: buscar lead por email
        stmt = select(Lead).where(Lead.emails.contains([email]))
        lead = (await session.execute(stmt)).scalar_one_or_none()
        if lead is not None:
            lead.status = LeadStatus.OPTED_OUT
            await session.delete(lead)

    await session.commit()

    html = _CONFIRMATION_HTML.format(
        contact=settings.company_contact_email,
        privacy=settings.company_privacy_policy_url,
    )
    return HTMLResponse(content=html, status_code=200)
