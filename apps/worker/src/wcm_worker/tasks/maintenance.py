"""Tasks de mantenimiento periódico (Celery beat).

`wcm.maintenance.retention_sweep` aplica la política de retención de
`apps/api/legal/politica_retencion.md`:

- Leads DISCOVERED sin outreach_sequences ni audit_log SEND ⇒ borrar
  pasados 12 meses desde created_at.
- Leads OUTREACH_SENT sin respuesta tras 24 meses ⇒ status DISCARDED.
  Pasados 6 meses adicionales en DISCARDED ⇒ borrar.
- opt_out_log NUNCA se borra (base jurídica para no recontactar).
- error_log con `at < now() - 90d` ⇒ borrar.

Idempotente. Si nada cumple criterios, no toca nada. Cada ejecución
escribe un audit_log con `actor='retention-sweep'`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, exists, or_, select, update
from wcm_db.models.audit import AuditLog, ErrorLog
from wcm_db.models.leads import Lead
from wcm_db.models.outreach import OutreachSequence
from wcm_types.enums import AuditAction, LeadStatus

from wcm_worker.celery_app import celery_app
from wcm_worker.db import session_scope

log = logging.getLogger("wcm.worker.tasks.maintenance")

DISCOVERED_TTL_DAYS = 365
OUTREACH_NO_REPLY_TTL_DAYS = 24 * 30  # 24 meses
DISCARDED_TTL_DAYS = 6 * 30  # 6 meses extra antes de borrar definitivamente
ERROR_LOG_TTL_DAYS = 90


@celery_app.task(name="wcm.maintenance.retention_sweep", bind=True, max_retries=0)
def retention_sweep(self) -> dict:
    """Aplica la política de retención. Llamada por Celery beat 1x/día."""
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        stats = {
            "leads_discovered_purged": _purge_stale_discovered(session, now),
            "leads_outreach_to_discarded": _move_outreach_to_discarded(session, now),
            "leads_discarded_purged": _purge_old_discarded(session, now),
            "error_logs_purged": _purge_error_logs(session, now),
        }
        session.add(
            AuditLog(
                actor="retention-sweep",
                action=AuditAction.DELETE,
                entity_type="maintenance",
                entity_id=None,
                payload={"stats": stats, "at": now.isoformat()},
            )
        )
        log.info("retention_sweep_complete", extra=stats)
        return {"status": "ok", "stats": stats}


def _purge_stale_discovered(session, now: datetime) -> int:
    """Borra leads en DISCOVERED creados hace >12 meses sin outreach."""
    threshold = now - timedelta(days=DISCOVERED_TTL_DAYS)
    has_sequence = exists().where(OutreachSequence.lead_id == Lead.id)
    stmt = (
        delete(Lead)
        .where(
            and_(
                Lead.status == LeadStatus.DISCOVERED,
                Lead.created_at < threshold,
                ~has_sequence,
            )
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def _move_outreach_to_discarded(session, now: datetime) -> int:
    """Marca como DISCARDED los leads enviados hace >24 meses sin respuesta."""
    threshold = now - timedelta(days=OUTREACH_NO_REPLY_TTL_DAYS)
    stmt = (
        update(Lead)
        .where(
            and_(
                Lead.status == LeadStatus.OUTREACH_SENT,
                Lead.updated_at < threshold,
            )
        )
        .values(status=LeadStatus.DISCARDED)
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def _purge_old_discarded(session, now: datetime) -> int:
    """Borra leads DISCARDED >6 meses."""
    threshold = now - timedelta(days=DISCARDED_TTL_DAYS)
    stmt = (
        delete(Lead)
        .where(
            and_(
                Lead.status == LeadStatus.DISCARDED,
                Lead.updated_at < threshold,
            )
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def _purge_error_logs(session, now: datetime) -> int:
    threshold = now - timedelta(days=ERROR_LOG_TTL_DAYS)
    stmt = (
        delete(ErrorLog)
        .where(ErrorLog.at < threshold)
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)
