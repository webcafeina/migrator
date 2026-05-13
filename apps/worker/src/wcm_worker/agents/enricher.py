"""EnricherAgent — extracción de emails/teléfonos/socials + embedding semántico.

Pobla `lead.emails`, `lead.phones`, `lead.social_links`, `lead.score` y el
vector `lead.embedding` (1024 dim, sentence-transformers e5-large).

Fase 9 amplió la versión MVP con:
- Cálculo de embedding para búsqueda semántica de leads similares.
- AuditLog ENRICH con legal_ground 6.1.f.

El embedding se puede desactivar en tests con `ctx.extra["skip_embedding"]=True`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx
from wcm_db.models.audit import AuditLog
from wcm_db.models.leads import Lead
from wcm_types.enums import AuditAction, LeadStatus

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import EnricherError

log = logging.getLogger("wcm.worker.enricher")

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

        embedding_info: dict[str, object] = {"computed": False}
        if not ctx.extra.get("skip_embedding"):
            try:
                embedding_info = self._compute_embedding(lead, html_blob)
            except Exception as e:  # noqa: BLE001
                # Embedding nunca debe tirar el enrichment entero abajo.
                log.warning("embedding_unexpected_error", extra={"error": str(e)})
                embedding_info = {"computed": False, "reason": f"unexpected: {e}"}

        ctx.session.add(
            AuditLog(
                actor="enricher",
                action=AuditAction.ENRICH,
                entity_type="lead",
                entity_id=str(lead.id),
                legal_ground="6.1.f",
                payload={
                    "emails_count": len(lead.emails),
                    "phones_count": len(lead.phones),
                    "socials": list(social_links.keys()),
                    "score": lead.score,
                    "embedding": embedding_info,
                },
            )
        )

        ctx.session.flush()
        return AgentResult(
            summary=f"{lead.url}: {len(emails)} emails, {len(phones)} phones, "
                    f"{len(social_links)} socials, score={lead.score}, "
                    f"embedding={'yes' if embedding_info.get('computed') else 'no'}",
            outputs={
                "emails": lead.emails,
                "phones": lead.phones,
                "socials": list(social_links.keys()),
                "score": lead.score,
                "embedding": embedding_info,
            },
        )

    def _compute_embedding(self, lead: Lead, html_blob: str) -> dict[str, object]:
        """Calcula y persiste el embedding del lead.

        El texto fuente combina business_name + sector + region + un snippet
        del HTML (primeros 1500 chars de texto plano aprox). Si el servicio
        falla por dep no instalada o error transitorio, se loggea y se
        continúa sin embedding (no es bloqueante).
        """
        try:
            from wcm_worker.embedding import (  # import perezoso
                DEFAULT_MODEL,
                EmbeddingService,
                get_embedding_service,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("embedding_import_failed", extra={"error": str(e)})
            return {"computed": False, "reason": f"import_error: {e}"}

        text = _build_embedding_text(lead, html_blob)
        if not text.strip():
            return {"computed": False, "reason": "empty_text"}

        try:
            service = get_embedding_service()
            vec = service.embed_text(text)
        except Exception as e:  # noqa: BLE001
            log.warning("embedding_compute_failed", extra={"error": str(e)})
            return {"computed": False, "reason": f"compute_error: {e}"}

        if len(vec) != 1024:
            log.error("embedding_dim_mismatch", extra={"dim": len(vec)})
            return {"computed": False, "reason": f"dim_mismatch_{len(vec)}"}

        lead.embedding = vec
        lead.embedding_model = service.model_name or DEFAULT_MODEL
        lead.embedding_at = datetime.now(timezone.utc)
        return {
            "computed": True,
            "model": lead.embedding_model,
            "dim": len(vec),
            "source_chars": len(text),
        }

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


#: Regex grosera para extraer texto visible del HTML. No es un parser DOM
#: real — para enriquecimiento basta con quitar tags y compactar espacios.
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _build_embedding_text(lead: Lead, html_blob: str) -> str:
    """Construye el texto fuente para el embedding.

    Formato: `<business> | <sector> en <region> | builder=<x> | <snippet>`.
    El builder ayuda a clusterizar leads por origen tecnológico.
    """
    parts: list[str] = []
    if lead.business_name:
        parts.append(lead.business_name)
    if lead.sector:
        parts.append(f"sector: {lead.sector}")
    if lead.region:
        parts.append(f"región: {lead.region}")
    if lead.builder_detected:
        builder_name = (
            lead.builder_detected.value
            if hasattr(lead.builder_detected, "value")
            else str(lead.builder_detected)
        )
        parts.append(f"builder: {builder_name}")
    snippet = _html_to_text_snippet(html_blob, max_chars=1500)
    if snippet:
        parts.append(snippet)
    return " | ".join(parts)


def _html_to_text_snippet(html: str, *, max_chars: int) -> str:
    """Strip de tags + colapso de whitespace. Conserva el primer párrafo
    visible — suficiente para captura semántica del lead.
    """
    if not html:
        return ""
    no_scripts = _TAG_RE.sub(" ", html)
    text = _HTML_RE.sub(" ", no_scripts)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


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
