"""Health y readiness probes.

- `/health`: el proceso responde. Cheap, no toca dependencias.
- `/ready`: BD responde a SELECT 1. Compatible con probes Nginx/k8s.
- `/health/deep`: comprueba **todas** las dependencias críticas
  (Postgres, Redis, R2). Útil como dashboard de estado y para
  diagnóstico en runbooks. Cada dep se mide individualmente.

Ambas sin auth — son endpoints internos para Nginx y monitoreo.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from wcm_api.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def ready(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Comprueba que la BD responde a SELECT 1. Si falla, retorna 503."""
    from fastapi import HTTPException

    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"db": "unavailable", "error": str(e)[:200]},
        ) from e
    return {"status": "ready", "db": "ok"}


@router.get("/health/deep")
async def health_deep(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Comprueba todas las dependencias críticas.

    Cada check es independiente; el overall_status es "ok" si todos
    los críticos están ok; "degraded" si alguno opcional falla; "fail"
    si alguno crítico falla.
    """
    db = await _check_db(session)
    redis_status = await _check_redis()
    r2 = _check_r2()

    critical = {"db": db, "redis": redis_status}
    optional = {"r2": r2}

    overall = "ok"
    for check in critical.values():
        if check["status"] not in ("ok", "skipped"):
            overall = "fail"
            break
    if overall == "ok":
        for check in optional.values():
            if check["status"] == "fail":
                overall = "degraded"
                break

    return {
        "status": overall,
        "checks": {**critical, **optional},
    }


# ---------- checkers ----------

async def _check_db(session: AsyncSession) -> dict:
    start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": str(e)[:200]}


async def _check_redis() -> dict:
    """Ping Redis vía la URL configurada. Si no hay `REDIS_URL`, "skipped"."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return {"status": "skipped", "reason": "REDIS_URL no configurado"}
    try:
        from redis.asyncio import Redis  # type: ignore
    except ImportError:
        return {"status": "skipped", "reason": "redis-py no instalado"}

    start = time.perf_counter()
    try:
        client = Redis.from_url(url, socket_timeout=2.0)
        pong = await asyncio.wait_for(client.ping(), timeout=2.5)
        await client.aclose()
        if not pong:
            return {"status": "fail", "error": "PING devolvió falsy"}
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": str(e)[:200]}


def _check_r2() -> dict:
    """head_bucket sobre el bucket configurado. Si no hay credenciales,
    "skipped" (R2 es opcional para el funcionamiento del producto).
    """
    bucket = os.environ.get("R2_BUCKET", "").strip()
    if not bucket:
        return {"status": "skipped", "reason": "R2 no configurado"}
    try:
        from wcm_worker.integrations.r2 import R2Client
    except ImportError:
        return {"status": "skipped", "reason": "worker module no disponible"}

    client = R2Client.from_env()
    if client is None:
        return {"status": "skipped", "reason": "credenciales R2 incompletas"}

    start = time.perf_counter()
    try:
        client._s3.head_bucket(Bucket=bucket)  # noqa: SLF001
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": str(e)[:200]}
