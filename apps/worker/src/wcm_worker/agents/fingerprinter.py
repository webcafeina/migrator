"""FingerprinterAgent — wrapper sobre wcm_scraper_core.fingerprint.

Toma un Lead.url, hace GET HTTP simple (sin browser), aplica patterns.yml
y persiste builder_detected + builder_confidence + builder_evidence.

Real, ejecutable. Para fingerprint con renderizado JS (nivel 4-5) se
amplía en futuras fases con Playwright.
"""

from __future__ import annotations

import httpx

from wcm_db.models.leads import Lead
from wcm_scraper_core.fingerprint import fingerprint_url
from wcm_types.enums import BuilderType
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import FingerprinterError


class FingerprinterAgent(BaseAgent):
    name = "fingerprinter"
    phase_name = "fingerprint"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.lead_id is None:
            raise FingerprinterError("FingerprinterAgent requiere lead_id en el contexto")

        lead = ctx.session.get(Lead, ctx.lead_id)
        if lead is None:
            raise FingerprinterError(f"Lead {ctx.lead_id} no encontrado")

        url = lead.url
        # Sin browser — fingerprint de niveles 1-3 es suficiente para clasificar
        # la mayoría de webs. Si la confianza es baja, en versiones futuras se
        # escala a `lsr-fingerprint` con Playwright.
        try:
            resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        except httpx.RequestError as e:
            raise FingerprinterError(f"URL inalcanzable: {e}") from e

        result = fingerprint_url(html=resp.text, headers=dict(resp.headers))
        best = result.best_builder()

        if best is None:
            lead.builder_detected = BuilderType.UNKNOWN
            lead.builder_confidence = 0.0
            lead.builder_evidence = []
        else:
            try:
                lead.builder_detected = BuilderType(_normalize_builder_name(best.name))
            except ValueError:
                lead.builder_detected = BuilderType.OTHER
            lead.builder_confidence = float(best.confidence)
            lead.builder_evidence = [
                {"name": m.name, "category": m.category, "confidence": m.confidence,
                 "evidence": m.evidence}
                for m in result.matches[:5]
            ]

        ctx.session.flush()
        return AgentResult(
            summary=f"{lead.url} → {lead.builder_detected.value} (conf={lead.builder_confidence:.2f})",
            outputs={
                "builder": lead.builder_detected.value,
                "confidence": lead.builder_confidence,
                "matches": len(result.matches),
            },
        )


def _normalize_builder_name(name: str) -> str:
    """Mapea nombres de tech del patterns.yml a valores de BuilderType."""
    mapping = {
        "Wix": "wix",
        "Hostinger AI Builder": "hostinger_ai",
        "Webflow": "webflow",
        "WordPress": "wordpress",
        "Squarespace": "squarespace",
        "Shopify": "shopify",
    }
    return mapping.get(name, "other")
