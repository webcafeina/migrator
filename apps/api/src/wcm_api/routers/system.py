"""Información de runtime del API para el panel /settings del dashboard.

Solo lectura. Devuelve datos no sensibles que un operador necesita ver
de un vistazo al abrir Ajustes: versión deployada, entorno, revisión
de Alembic aplicada en la BD, uptime y resumen de health de las
dependencias críticas.

RBAC admin/operator — los detalles incluyen la revision de Alembic y
component paths que viewers no necesitan ver.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.config import get_settings
from wcm_api.db import get_session
from wcm_api.routers.health import _check_db, _check_r2, _check_redis
from wcm_api.security import require_role
from wcm_types.enums import UserRole

router = APIRouter(prefix="/system", tags=["system"])

_admin_or_operator = require_role(UserRole.ADMIN.value, UserRole.OPERATOR.value)

# Capturado al importar el módulo — basta para el cálculo de uptime
# del proceso uvicorn. No es persistente (cada reinicio resetea), que
# es exactamente lo que el operador quiere ver tras un `systemctl
# restart webcafeina-api`.
_PROCESS_STARTED_AT: datetime = datetime.now(UTC)


HealthStatus = Literal["ok", "fail", "skipped"]
OverallHealth = Literal["ok", "degraded", "fail"]


class HealthSummary(BaseModel):
    """Resumen plano del health para /settings — solo status por dep
    (sin latencias, sin errores). Para diagnóstico detallado, el
    endpoint `/health/deep` sigue siendo la fuente canónica."""

    overall: OverallHealth
    db: HealthStatus
    redis: HealthStatus
    r2: HealthStatus


class FirmaInfo(BaseModel):
    """Firma legal + datos de empresa del producto (read-only desde
    dashboard). El operador puede ver qué firma se está aplicando a
    los borradores de contacto sin SSHear al servidor; para editarla
    sigue siendo necesario tocar `.env` (decisión v0.12.0)."""

    company_legal_name: str
    company_cif: str | None
    company_address: str | None
    company_contact_email: str
    company_privacy_policy_url: str
    opt_out_url_base: str


class SystemInfo(BaseModel):
    """Runtime del API. Datos no sensibles aptos para mostrar en UI."""

    version: str = Field(description="Versión del paquete wcm-api.")
    environment: str = Field(description="Entorno (dev/staging/prod).")
    python_version: str = Field(description="Python `X.Y.Z`.")
    alembic_revision: str | None = Field(
        description="Revision de Alembic aplicada en la BD; null si la "
        "tabla `alembic_version` no existe (BD sin migraciones)."
    )
    uptime_seconds: int = Field(
        ge=0, description="Segundos desde el último arranque del proceso."
    )
    health: HealthSummary


@router.get("/info", response_model=SystemInfo)
async def system_info(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[object, Depends(_admin_or_operator)],
) -> SystemInfo:
    """Info de runtime para `/settings` del dashboard.

    Sin parámetros — el endpoint refleja el estado AHORA del proceso
    que sirve la request. Si hay múltiples workers tras un reverse
    proxy, cada uno responderá con su propio uptime/health.
    """
    settings = get_settings()

    try:
        ver = pkg_version("wcm-api")
    except PackageNotFoundError:  # pragma: no cover — solo en sandbox sin install
        ver = "0.0.0+unknown"

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    revision = await _alembic_revision(session)
    uptime = int((datetime.now(UTC) - _PROCESS_STARTED_AT).total_seconds())
    health = await _health_summary(session)

    return SystemInfo(
        version=ver,
        environment=settings.env,
        python_version=py,
        alembic_revision=revision,
        uptime_seconds=uptime,
        health=health,
    )


async def _alembic_revision(session: AsyncSession) -> str | None:
    """Lee la revision aplicada en la BD. Si la tabla no existe
    devolvemos None — la BD existe pero nunca corrió `alembic upgrade`.
    """
    try:
        result = await session.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        row = result.first()
        return row[0] if row else None
    except Exception:  # noqa: BLE001 — tabla no existe / BD inalcanzable
        return None


async def _health_summary(session: AsyncSession) -> HealthSummary:
    """Versión condensada de `/health/deep` — solo status por dep.
    Reúsa los checkers existentes para mantener una sola fuente de
    verdad sobre qué consideramos sano.
    """
    db = await _check_db(session)
    redis = await _check_redis()
    r2 = _check_r2()

    db_status: HealthStatus = db["status"]
    redis_status: HealthStatus = redis["status"]
    r2_status: HealthStatus = r2["status"]

    # Mismo criterio que /health/deep: críticos (db, redis) gobiernan
    # overall=fail; r2 opcional → degraded si falla.
    overall: OverallHealth = "ok"
    if db_status == "fail" or redis_status == "fail":
        overall = "fail"
    elif r2_status == "fail":
        overall = "degraded"

    return HealthSummary(
        overall=overall,
        db=db_status,
        redis=redis_status,
        r2=r2_status,
    )


@router.get("/firma", response_model=FirmaInfo)
async def system_firma(
    _: Annotated[object, Depends(_admin_or_operator)],
) -> FirmaInfo:
    """Firma legal aplicada a los borradores de contacto. Read-only.
    `COMPANY_CIF` y `COMPANY_ADDRESS` se leen directamente de env
    vars (NO viven en ApiSettings — los consume el composer worker
    via os.environ)."""
    settings = get_settings()
    return FirmaInfo(
        company_legal_name=settings.company_legal_name,
        company_cif=os.environ.get("COMPANY_CIF") or None,
        company_address=os.environ.get("COMPANY_ADDRESS") or None,
        company_contact_email=settings.company_contact_email,
        company_privacy_policy_url=settings.company_privacy_policy_url,
        opt_out_url_base=settings.outreach_opt_out_url_base,
    )
