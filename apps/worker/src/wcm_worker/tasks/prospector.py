"""Task Celery `wcm.prospector.run_campaign`.

Stub MVP. La implementación real (Google Maps API + directory-scraper +
dorks) llega en Fase 9.
"""

from __future__ import annotations

import logging

from wcm_worker.celery_app import celery_app

log = logging.getLogger("wcm.worker.tasks.prospector")


@celery_app.task(name="wcm.prospector.run_campaign", bind=True, max_retries=0)
def run_campaign(
    self,
    sector: str,
    region: str,
    target_count: int = 50,
    exclude_domains: list[str] | None = None,
) -> dict:
    log.warning(
        "prospector_stub_called",
        extra={"sector": sector, "region": region, "target_count": target_count},
    )
    return {
        "status": "not_implemented",
        "message": (
            "ProspectorAgent stubeado en Fase 6. Implementación real en Fase 9 "
            "(Google Maps API + directory-scraper + dorks + gdpr-compliance)."
        ),
        "sector": sector,
        "region": region,
        "target_count": target_count,
        "leads_discovered": 0,
    }
