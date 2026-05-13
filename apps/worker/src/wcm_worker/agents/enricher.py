"""EnricherAgent — extracción básica de emails/teléfonos del HTML del lead.

MVP funcional sin servicios externos. Se llama tras fingerprinter para
poblar `lead.emails`, `lead.phones`, `lead.social_links`.

Fase 9 (Prospección) lo ampliará con datos públicos de empresa
(LinkedIn público, estimación de empleados, etc.) bajo base jurídica
RGPD documentada (skill gdpr-compliance).
"""

from __future__ import annotations

import re

import httpx
from wcm_db.models.leads import Lead
from wcm_types.enums import LeadStatus

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import EnricherError

#: Regex de email con guardas anti-placeholder.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PLACEHOLDER_EMAILS = frozenset({"info@example.com", "test@test.com", "user@example.com"})

#: Teléfono España: +34 / 0034 / sin prefijo. Móvil (6/7) o fijo (8/9).
_PHONE_RE = re.compile(r"(?:\+34|0034)?[ \-]?[6789]\d{2}[ \-]?\d{3}[ \-]?\d{3}")

#: URLs de redes sociales.
_SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+"),
    "instagram": re.compile(r"instagram\.com/[a-zA-Z0-9._-]+"),
    "facebook": re.compile(r"facebook\.com/[a-zA-Z0-9._-]+"),
    "twitter": re.compile(r"(?:twitter\.com|x\.com)/[a-zA-Z0-9._-]+"),
    "youtube": re.compile(r"youtube\.com/(?:c|channel|user|@)/[a-zA-Z0-9._-]+"),
    "tiktok": re.compile(r"tiktok\.com/@[a-zA-Z0-9._-]+"),
}


class EnricherAgent(BaseAgent):
    name = "enricher"
    phase_name = "enrich"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.lead_id is None:
            raise EnricherError("EnricherAgent requiere lead_id en el contexto")

        lead = ctx.session.get(Lead, ctx.lead_id)
        if lead is None:
            raise EnricherError(f"Lead {ctx.lead_id} no encontrado")

        # Recolectar HTML de home + páginas de contacto/aviso-legal típicas.
        html_blob = self._collect_html(lead.url)

        emails = self._extract_emails(html_blob, domain_hint=lead.url)
        phones = self._extract_phones(html_blob)
        social_links = self._extract_socials(html_blob)

        lead.emails = sorted(set(emails))
        lead.phones = sorted(set(phones))
        lead.social_links = social_links
        lead.status = LeadStatus.ENRICHED
        lead.score = _compute_score(lead)

        ctx.session.flush()
        return AgentResult(
            summary=f"{lead.url}: {len(emails)} emails, {len(phones)} phones, "
                    f"{len(social_links)} socials, score={lead.score}",
            outputs={
                "emails": lead.emails,
                "phones": lead.phones,
                "socials": list(social_links.keys()),
                "score": lead.score,
            },
        )

    # ---------- helpers ----------

    def _collect_html(self, base_url: str) -> str:
        """Concatena HTML de home + páginas de contacto/legales típicas."""
        candidates = ["", "/contacto", "/contact", "/aviso-legal", "/legal", "/politica-de-privacidad"]
        chunks: list[str] = []
        for path in candidates:
            url = base_url.rstrip("/") + path
            try:
                r = httpx.get(url, timeout=10.0, follow_redirects=True)
                if r.status_code == 200:
                    chunks.append(r.text)
            except httpx.RequestError:
                continue
        return "\n".join(chunks)

    def _extract_emails(self, html: str, *, domain_hint: str) -> list[str]:
        found = _EMAIL_RE.findall(html)
        return [e for e in found if e.lower() not in _PLACEHOLDER_EMAILS]

    def _extract_phones(self, html: str) -> list[str]:
        return [_normalize_phone(p) for p in _PHONE_RE.findall(html)]

    def _extract_socials(self, html: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for net, regex in _SOCIAL_PATTERNS.items():
            m = regex.search(html)
            if m:
                out[net] = "https://" + m.group(0)
        return out


def _normalize_phone(raw: str) -> str:
    """Normaliza espacios/guiones. Añade +34 si no llevaba prefijo."""
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+34") or digits.startswith("0034"):
        return digits
    if len(digits) == 9 and digits[0] in "6789":
        return f"+34{digits}"
    return digits


def _compute_score(lead: Lead) -> int:
    """Score 0-100 según señales acumuladas. Heurística MVP."""
    score = 0
    if lead.builder_detected and lead.builder_confidence and lead.builder_confidence >= 0.7:
        score += 20
    if lead.emails:
        score += 15
    if lead.phones:
        score += 10
    if lead.social_links:
        score += 5
    if lead.sector:
        score += 10
    return min(score, 100)
