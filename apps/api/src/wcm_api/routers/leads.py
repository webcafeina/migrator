"""Endpoints de leads (lectura + actualización manual + reasignación).

El descubrimiento masivo lo hace el worker (`enqueue_prospect_campaign`).
Aquí solo exponemos lectura y operaciones puntuales (corregir manualmente,
disparar re-fingerprint, etc.).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.config import ApiSettings, get_settings
from wcm_api.db import get_session
from wcm_api.errors import ConflictError, NotFoundError
from wcm_api.rate_limit import limiter
from wcm_api.security import (
    TokenPayload,
    get_current_user_payload,
    issue_opt_out_token,
    require_role,
)
from wcm_api.tasks.enqueue import (
    enqueue_lead_enrich,
    enqueue_lead_fingerprint,
    enqueue_outreach_compose,
)
from wcm_db.models.audit import AuditLog
from wcm_db.models.leads import Lead
from wcm_scraper_core.urls import normalize_lead_url
from wcm_types.enums import AuditAction, BuilderType, LeadStatus, UserRole
from wcm_types.schemas.leads import (
    LeadBulkCreate,
    LeadBulkCreateOutcome,
    LeadBulkCreateResult,
    LeadCreate,
    LeadRead,
    LeadUpdate,
)

router = APIRouter(prefix="/leads", tags=["leads"])

_any_user = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value)
_operator_or_admin = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)


@router.get("", response_model=list[LeadRead])
async def list_leads(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
    sector: str | None = Query(default=None),
    region: str | None = Query(default=None),
    builder: BuilderType | None = Query(default=None),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[LeadRead]:
    stmt = select(Lead)
    if sector:
        stmt = stmt.where(Lead.sector == sector)
    if region:
        stmt = stmt.where(Lead.region == region)
    if builder:
        stmt = stmt.where(Lead.builder_detected == builder)
    if status_filter:
        # Filtro explícito: respeta el status pedido (incluye DISCARDED
        # si el operador lo selecciona vía el chip "Descartados").
        stmt = stmt.where(Lead.status == status_filter)
    else:
        # Default: oculta DISCARDED del listado para no llenar la
        # vista con ruido tras descartes masivos. Sigue accesible vía
        # `?status=discarded`.
        stmt = stmt.where(Lead.status != LeadStatus.DISCARDED)
    if min_score > 0:
        stmt = stmt.where(Lead.score >= min_score)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    leads = (await session.execute(stmt)).scalars().all()
    return [LeadRead.model_validate(lead) for lead in leads]


@router.get("/count")
async def count_leads(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> dict:
    total = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
    return {"total": int(total)}


class LeadStats(BaseModel):
    """Agregados del pipeline de leads para alimentar topbar/overview.

    `uncontacted` cuenta los leads en estado previo al outreach
    (`DISCOVERED`, `FINGERPRINTED`, `ENRICHED`). Los siguientes (`OUTREACH_*`,
    `RESPONDED`, `CONVERTED`, terminales) ya han recibido al menos una acción.
    `avg_score` excluye filas con `score=0` (típicamente leads recién
    descubiertos sin fingerprint). `distinct_builders` excluye `null` y
    `unknown`, que no aportan información de stack.
    """

    total: int = Field(description="Leads totales en el pipeline.")
    uncontacted: int = Field(description="Leads en estado pre-outreach.")
    avg_score: float | None = Field(description="Score medio (0..100); null si no hay datos.")
    distinct_builders: int = Field(description="Builders únicos detectados, sin contar unknown/null.")
    distinct_sectors: int
    distinct_regions: int


_UNCONTACTED_STATUSES = (
    LeadStatus.DISCOVERED,
    LeadStatus.FINGERPRINTED,
    LeadStatus.ENRICHED,
)


@router.get("/stats", response_model=LeadStats)
async def lead_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> LeadStats:
    """Devuelve agregados del pipeline para el topbar de `/leads` y el panel."""
    total = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
    uncontacted = (
        await session.execute(
            select(func.count())
            .select_from(Lead)
            .where(Lead.status.in_(_UNCONTACTED_STATUSES))
        )
    ).scalar_one()
    avg_score_raw = (
        await session.execute(
            select(func.avg(Lead.score)).where(Lead.score > 0)
        )
    ).scalar_one_or_none()
    distinct_builders = (
        await session.execute(
            select(func.count(func.distinct(Lead.builder_detected)))
            .where(Lead.builder_detected.is_not(None))
            .where(Lead.builder_detected != BuilderType.UNKNOWN)
        )
    ).scalar_one()
    distinct_sectors = (
        await session.execute(
            select(func.count(func.distinct(Lead.sector))).where(Lead.sector.is_not(None))
        )
    ).scalar_one()
    distinct_regions = (
        await session.execute(
            select(func.count(func.distinct(Lead.region))).where(Lead.region.is_not(None))
        )
    ).scalar_one()
    return LeadStats(
        total=int(total),
        uncontacted=int(uncontacted),
        avg_score=float(avg_score_raw) if avg_score_raw is not None else None,
        distinct_builders=int(distinct_builders),
        distinct_sectors=int(distinct_sectors),
        distinct_regions=int(distinct_regions),
    )


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_any_user)],
) -> LeadRead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    return LeadRead.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> LeadRead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(lead, k, v)
    await session.commit()
    await session.refresh(lead)
    return LeadRead.model_validate(lead)


# ---------- Descarte / borrado de leads (v0.12.0) ----------


@router.post("/{lead_id}/discard", response_model=LeadRead)
async def discard_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> LeadRead:
    """Soft delete: marca el lead como DISCARDED. Reversible (basta con
    `PATCH /leads/{id}` poniendo status a otro valor). Mantiene la fila
    + enrichments + sequences para trazabilidad RGPD ("qué datos
    tuvimos sobre quién").

    Idempotente: si ya está DISCARDED, devuelve 200 sin tocar nada
    (sin AuditLog redundante).
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    if lead.status != LeadStatus.DISCARDED:
        lead.status = LeadStatus.DISCARDED
        session.add(
            AuditLog(
                actor=f"user:{user.sub}",
                action=AuditAction.UPDATE,
                entity_type="lead",
                entity_id=str(lead.id),
                legal_ground="6.1.f",
                payload={
                    "action": "discard",
                    "operator_role": user.role,
                },
            )
        )
        await session.commit()
        await session.refresh(lead)
    return LeadRead.model_validate(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> None:
    """Hard delete con CASCADE (vía relaciones SQLAlchemy
    `cascade="all, delete-orphan"` en `Lead.enrichments` y
    `Lead.outreach_sequences`, y `ondelete="CASCADE"` en las FKs).

    Útil para limpiar pruebas o cumplir el art. 17 RGPD (derecho de
    supresión). El AuditLog se escribe ANTES del delete (después no
    podríamos referenciar `entity_id` con sentido); el AuditLog
    persiste como evidencia del borrado conforme.
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")

    snapshot_url = lead.url
    snapshot_business_name = lead.business_name
    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=AuditAction.DELETE,
            entity_type="lead",
            entity_id=str(lead.id),
            legal_ground="6.1.f",
            payload={
                "action": "hard_delete",
                "snapshot_url": snapshot_url,
                "snapshot_business_name": snapshot_business_name,
                "operator_role": user.role,
            },
        )
    )
    await session.delete(lead)
    await session.commit()


# ---------- Alta manual de leads (single + bulk) ----------

async def _insert_lead(
    session: AsyncSession,
    *,
    raw_url: str,
    business_name: str | None,
    sector: str | None,
    region: str | None,
    country: str,
) -> tuple[Lead | None, int | None]:
    """INSERT ON CONFLICT DO NOTHING devolviendo `(lead, None)` si creado
    o `(None, existing_id)` si la URL ya existía.

    Helper compartido entre single y bulk para mantener la lógica de
    upsert canonicalizada en un solo sitio.
    """
    normalized = normalize_lead_url(raw_url)
    stmt = (
        pg_insert(Lead)
        .values(
            url=normalized,
            business_name=business_name,
            sector=sector,
            region=region,
            country=country,
            status=LeadStatus.DISCOVERED,
        )
        .on_conflict_do_nothing(index_elements=["url"])
        .returning(Lead.id)
    )
    result = await session.execute(stmt)
    new_id = result.scalar_one_or_none()
    if new_id is None:
        existing = (
            await session.execute(select(Lead.id).where(Lead.url == normalized))
        ).scalar_one_or_none()
        return None, existing
    lead = await session.get(Lead, new_id)
    return lead, None


def _audit_manual_lead(
    *, user: TokenPayload, lead_id: int, source: str, extra: dict | None = None
) -> AuditLog:
    """AuditLog DISCOVER para alta manual. `legal_ground=6.1.f` igual que
    el ProspectorAgent: la base RGPD (interés legítimo B2B) NO cambia
    por procedencia. La procedencia va en `payload.source`.
    """
    payload: dict = {
        "source": source,
        "operator_role": user.role,
    }
    if extra:
        payload.update(extra)
    return AuditLog(
        actor=f"user:{user.sub}",
        action=AuditAction.DISCOVER,
        entity_type="lead",
        entity_id=str(lead_id),
        legal_ground="6.1.f",
        payload=payload,
    )


def _enqueue_post_create_pipeline(lead_id: int) -> list[str]:
    """Fire-and-forget de fingerprint + enrich tras alta. Devuelve lista
    de warnings (vacía si todo OK). Si Celery está caído, devolvemos
    warning pero NO propagamos — el lead ya está persistido y el
    operador puede disparar manualmente desde la ficha.
    """
    warnings: list[str] = []
    try:
        enqueue_lead_fingerprint(lead_id)
    except Exception as e:  # noqa: BLE001 — log + degradación grácil
        warnings.append(f"enqueue_fingerprint_failed: {type(e).__name__}")
    try:
        enqueue_lead_enrich(lead_id, skip_embedding=False)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"enqueue_enrich_failed: {type(e).__name__}")
    return warnings


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead_manual(
    payload: LeadCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> LeadRead:
    """Alta manual de un lead. Encadena fingerprint+enrich fire-and-forget
    tras commit. Si la URL ya existe (UNIQUE), 409 con `existing_lead_id`
    en `details` para que el dashboard pueda navegar al existente.

    Base jurídica: art. 6.1.f RGPD (interés legítimo B2B), igual que la
    prospección automática. La procedencia queda registrada en el
    AuditLog (`payload.source="manual_dashboard"|"manual_cli"`).
    """
    lead, existing_id = await _insert_lead(
        session,
        raw_url=str(payload.url),
        business_name=payload.business_name,
        sector=payload.sector,
        region=payload.region,
        country=payload.country,
    )
    if lead is None:
        raise ConflictError(
            "Lead con esa URL ya existe",
            details={"existing_lead_id": existing_id},
        )
    # `source` lo deduce el cliente — el endpoint no sabe si vino del
    # dashboard o del CLI. Lo registramos genérico; el CLI puede
    # añadir un header X-Source-Channel en el futuro si interesa.
    session.add(
        _audit_manual_lead(
            user=user,
            lead_id=lead.id,
            source="manual_single",
        )
    )
    await session.commit()
    await session.refresh(lead)
    _enqueue_post_create_pipeline(lead.id)
    return LeadRead.model_validate(lead)


@router.post("/bulk", response_model=LeadBulkCreateResult)
@limiter.limit("10/minute")
async def create_leads_bulk(
    request: Request,
    payload: LeadBulkCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> LeadBulkCreateResult:
    """Alta masiva de leads. NO aborta el batch ante fallos aislados —
    cada URL se procesa de forma independiente vía `INSERT ON CONFLICT`.

    Devuelve listas separadas (`created`, `skipped_duplicates`, `failed`)
    para que el dashboard renderice el resumen sin filtrar por outcome.
    """
    created: list[Lead] = []
    skipped: list[LeadBulkCreateOutcome] = []
    failed: list[LeadBulkCreateOutcome] = []

    for raw_url in payload.urls:
        url_str = str(raw_url)
        try:
            lead, existing_id = await _insert_lead(
                session,
                raw_url=url_str,
                business_name=payload.business_name,
                sector=payload.sector,
                region=payload.region,
                country=payload.country,
            )
        except Exception as e:  # noqa: BLE001 — URL inesperadamente mala
            failed.append(LeadBulkCreateOutcome(
                url=url_str, outcome="failed", reason=type(e).__name__,
            ))
            continue
        if lead is None:
            skipped.append(LeadBulkCreateOutcome(
                url=url_str,
                outcome="skipped_duplicate",
                lead_id=existing_id,
            ))
            continue
        created.append(lead)
        session.add(_audit_manual_lead(
            user=user,
            lead_id=lead.id,
            source="manual_bulk",
            extra={"batch_size": len(payload.urls)},
        ))

    await session.commit()
    # Refresh + encolar tras commit único del batch.
    for lead in created:
        await session.refresh(lead)
        _enqueue_post_create_pipeline(lead.id)

    return LeadBulkCreateResult(
        created=[LeadRead.model_validate(lead) for lead in created],
        skipped_duplicates=skipped,
        failed=failed,
    )


@router.post("/{lead_id}/refingerprint", status_code=status.HTTP_202_ACCEPTED)
async def refingerprint_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    task_id = enqueue_lead_fingerprint(lead_id)
    return {"task_id": task_id, "status": "queued"}


@router.post("/{lead_id}/enrich", status_code=status.HTTP_202_ACCEPTED)
async def enrich_lead(
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_operator_or_admin)],
    skip_embedding: bool = Query(default=False, description="Saltar embedding (útil para tests/dev)"),
) -> dict:
    """Encola re-enrichment del lead (emails / phones / socials / embedding)."""
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    task_id = enqueue_lead_enrich(lead_id, skip_embedding=skip_embedding)
    return {"task_id": task_id, "status": "queued"}


# ---------- RGPD: opt-out URL, consent, outreach compose ----------

class OptOutUrlResponse(BaseModel):
    lead_id: int
    email: str
    url: str = Field(description="URL pública firmada para opt-out con un clic")


@router.post("/{lead_id}/opt-out-url", response_model=OptOutUrlResponse)
@limiter.limit("30/minute")
async def generate_opt_out_url(
    request: Request,
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
    _: Annotated[object, Depends(_operator_or_admin)],
    email: str | None = Query(default=None, description="Email destino; si vacío usa el primero del lead"),
) -> OptOutUrlResponse:
    """Genera la URL firmada de opt-out para incluir en outreach.

    No persiste nada — el token JWT es self-contained. El operador puede
    generar la URL para previsualizar o copiarla manualmente.
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    target_email = email or (lead.emails[0] if lead.emails else None)
    if not target_email:
        raise ConflictError(
            "Lead sin emails — enriquecimiento previo necesario antes de generar opt-out URL"
        )
    token = issue_opt_out_token(email=target_email, lead_id=lead.id, settings=settings)
    url = f"{settings.outreach_opt_out_url_base}?token={token}"
    return OptOutUrlResponse(lead_id=lead.id, email=target_email, url=url)


class ConsentRecord(BaseModel):
    """Registro manual de consent/oposición por parte de un operador.

    Para casos donde el lead nos responde por teléfono/whatsapp/email
    pidiendo NO ser contactado, o cuando consiente explícitamente.
    """

    action: Literal["consent_granted", "objection_received", "manual_review"]
    legal_ground: str = Field(default="6.1.f", max_length=40)
    note: str | None = Field(default=None, max_length=1000)


@router.post("/{lead_id}/consent", status_code=status.HTTP_201_CREATED)
async def record_consent_action(
    lead_id: int,
    payload: ConsentRecord,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[TokenPayload, Depends(get_current_user_payload)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """Persiste una acción manual de consent/oposición en `audit_log`.

    Si la acción es `objection_received`, también marca el lead como
    OPTED_OUT (y lo borra cascadamente como hace `/opt-out` público —
    diferencia: aquí mantenemos el lead en `MANUAL_REVIEW` para que el
    operador decida si borrarlo o solo pausar la secuencia).
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")

    audit_action = {
        "consent_granted": AuditAction.UPDATE,
        "objection_received": AuditAction.OPT_OUT,
        "manual_review": AuditAction.UPDATE,
    }[payload.action]

    if payload.action == "objection_received":
        lead.status = LeadStatus.OPTED_OUT
    elif payload.action == "manual_review":
        lead.status = LeadStatus.MANUAL_REVIEW

    session.add(
        AuditLog(
            actor=f"user:{user.sub}",
            action=audit_action,
            entity_type="lead",
            entity_id=str(lead.id),
            legal_ground=payload.legal_ground,
            payload={
                "manual_action": payload.action,
                "note": payload.note,
                "operator_role": user.role,
            },
        )
    )
    await session.commit()
    return {
        "lead_id": lead.id,
        "action": payload.action,
        "new_status": lead.status.value if hasattr(lead.status, "value") else str(lead.status),
    }


@router.post("/{lead_id}/outreach/compose", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def compose_outreach_for_lead(
    request: Request,
    lead_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[ApiSettings, Depends(get_settings)],
    _: Annotated[object, Depends(_operator_or_admin)],
) -> dict:
    """Encola el OutreachComposerAgent para generar el draft del lead.

    La API emite aquí el `opt_out_token` para no compartir `JWT_SECRET`
    con el worker. El worker solo renderiza la URL final.
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} no encontrado")
    if not lead.emails:
        raise ConflictError(
            "Lead sin emails — enriquecimiento previo necesario antes de componer outreach"
        )
    token = issue_opt_out_token(
        email=lead.emails[0], lead_id=lead.id, settings=settings
    )
    task_id = enqueue_outreach_compose(lead.id, opt_out_token=token)
    return {"task_id": task_id, "status": "queued", "lead_id": lead.id}
