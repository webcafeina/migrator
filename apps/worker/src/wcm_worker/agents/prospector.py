"""ProspectorAgent — descubrimiento de leads vía Google Places API.

Fase 9. Sustituye el stub previo. Flujo:

1. Construye query de Text Search a partir de `sector` + `region` del ctx.
2. Itera resultados de Google Places (legacy API).
3. Para cada lugar con `website` y no excluido por dominio:
   - Normaliza URL.
   - Hace `INSERT ... ON CONFLICT DO NOTHING` por la UNIQUE(url).
   - Persiste un AuditLog DISCOVER con `legal_ground=6.1.f` (interés
     legítimo RGPD art. 6.1.f) y entity_id del lead creado.
4. Persiste enriquecimiento ligero (rating + types + phone) en
   `lead_enrichments` con source=`google_maps`.

NO hace fingerprint ni embedding — esos pasos los hacen FingerprinterAgent
y EnricherAgent respectivamente, encadenados por el pipeline.

Output esperado en ctx.extra:
- `sector: str` (obligatorio)
- `region: str` (obligatorio)
- `target_count: int` (opcional, default 50)
- `exclude_domains: list[str]` (opcional, default [])
- `query_template: str` (opcional, default "{sector} en {region}")
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from sqlalchemy.dialects.postgresql import insert as pg_insert

from wcm_db.models.audit import AuditLog
from wcm_db.models.leads import Lead, LeadEnrichment
from wcm_scraper_core.directories import (
    GooglePlacesClient,
    GooglePlacesError,
    GooglePlacesQuotaExceeded,
    PlaceResult,
)
from wcm_types.enums import AuditAction, LeadStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ProspectorError

log = logging.getLogger("wcm.worker.prospector")

#: Google sirve 20 resultados/página. 3 páginas (60 leads) cubren la
#: mayoría de queries. target_count > 60 requeriría diversificar query.
_MAX_PAGES_PER_QUERY = 3

#: Tipos de Google Places que descartamos por irrelevantes para web
#: profesional (gas stations, parkings, atms, transit, etc.).
_BLOCKED_TYPES = frozenset({
    "gas_station", "atm", "parking", "bus_station", "transit_station",
    "subway_station", "train_station", "airport", "cemetery", "embassy",
    "fire_station", "hospital", "police", "courthouse", "city_hall",
})


class ProspectorAgent(BaseAgent):
    name = "prospector"
    phase_name = "prospect"

    def __init__(self, client: GooglePlacesClient | None = None) -> None:
        """`client` inyectable para tests. En prod se construye lazy desde env."""
        self._injected_client = client

    def run(self, ctx: AgentContext) -> AgentResult:
        sector = ctx.extra.get("sector")
        region = ctx.extra.get("region")
        target_count = int(ctx.extra.get("target_count", 50))
        exclude_domains = {d.lower().lstrip(".") for d in ctx.extra.get("exclude_domains", [])}
        query_template = ctx.extra.get("query_template", "{sector} en {region}")

        if not sector or not region:
            raise ProspectorError("ProspectorAgent requiere sector y region en ctx.extra")

        query = query_template.format(sector=sector, region=region)
        log.info("prospect_campaign_start", extra={
            "query": query, "target_count": target_count,
        })

        client = self._injected_client or _build_client_from_env()
        owns_client = self._injected_client is None

        discovered = 0
        created = 0
        skipped_no_website = 0
        skipped_excluded = 0
        skipped_blocked_type = 0
        skipped_duplicate = 0
        warnings: list[str] = []

        try:
            for place in client.text_search(query, max_pages=_MAX_PAGES_PER_QUERY):
                if discovered >= target_count:
                    break
                discovered += 1

                # Text Search legacy NO devuelve `website` ni `phone` —
                # solo place_id, name, address, types, rating. Para esos
                # campos hace falta llamar a place_details. Filtramos
                # por tipo PRIMERO (sin call extra), luego details.
                if _is_blocked_type(place):
                    skipped_blocked_type += 1
                    continue

                details = client.place_details(place.place_id)
                # `details` puede ser None si Google devolvió NOT_FOUND.
                # Usamos el merge: detalles completos si los hay, place
                # base si no (sin website, se descartará).
                place_full = details or place
                if not place_full.website:
                    skipped_no_website += 1
                    continue

                normalized_url = _normalize_url(place_full.website)
                domain = _domain_of(normalized_url)
                if not domain or domain in exclude_domains:
                    skipped_excluded += 1
                    continue

                lead_id = _upsert_lead(ctx, normalized_url, place_full, sector, region)
                if lead_id is None:
                    skipped_duplicate += 1
                    continue
                created += 1

                _insert_enrichment(ctx, lead_id, place_full)
                _audit_discover(ctx, lead_id, query, place_full)
        except GooglePlacesQuotaExceeded as e:
            warnings.append(f"Quota Google alcanzada: {e}")
            log.warning("prospect_quota_exceeded", extra={"error": str(e)})
        except GooglePlacesError as e:
            raise ProspectorError(f"Google Places falló: {e}") from e
        finally:
            if owns_client:
                client.close()

        # Flush para garantizar que el commit de session_scope vea todo.
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"query={query!r} discovered={discovered} created={created} "
                f"dup={skipped_duplicate} no_website={skipped_no_website} "
                f"excluded={skipped_excluded} blocked_type={skipped_blocked_type}"
            ),
            outputs={
                "query": query,
                "discovered": discovered,
                "created": created,
                "skipped_duplicate": skipped_duplicate,
                "skipped_no_website": skipped_no_website,
                "skipped_excluded": skipped_excluded,
                "skipped_blocked_type": skipped_blocked_type,
            },
            warnings=warnings,
        )


# ---------- helpers ----------

def _build_client_from_env() -> GooglePlacesClient:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ProspectorError(
            "GOOGLE_MAPS_API_KEY no definida — imposible lanzar prospección"
        )
    return GooglePlacesClient(
        api_key=api_key,
        base_url=os.environ.get(
            "GOOGLE_MAPS_API_BASE", "https://maps.googleapis.com/maps/api/place"
        ),
        language=os.environ.get("GOOGLE_MAPS_LANGUAGE", "es"),
        region=os.environ.get("GOOGLE_MAPS_REGION", "es"),
    )


def _normalize_url(url: str) -> str:
    """Canónica: scheme + lowercase host + path sin trailing slash inicial.

    No quitamos el path entero — algunos negocios tienen su web en
    `/inicio` o en una subruta. Sí quitamos UTM y fragments.
    """
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{host}{path}"


def _domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_blocked_type(place: PlaceResult) -> bool:
    return any(t in _BLOCKED_TYPES for t in place.types)


def _upsert_lead(
    ctx: AgentContext, url: str, place: PlaceResult, sector: str, region: str
) -> int | None:
    """INSERT ON CONFLICT DO NOTHING. Devuelve lead_id si nuevo, None si dup."""
    stmt = (
        pg_insert(Lead)
        .values(
            url=url,
            business_name=place.name or None,
            sector=sector,
            country="ES",
            region=region,
            status=LeadStatus.DISCOVERED,
            emails=[],
            phones=[place.phone] if place.phone else [],
            social_links={},
        )
        .on_conflict_do_nothing(index_elements=["url"])
        .returning(Lead.id)
    )
    res = ctx.session.execute(stmt).scalar_one_or_none()
    if res is None:
        # Conflict: lead ya existe. Devolvemos None y el caller cuenta dup.
        return None
    return int(res)


def _insert_enrichment(ctx: AgentContext, lead_id: int, place: PlaceResult) -> None:
    """Persiste el JSON de Google como `lead_enrichments` con source=google_maps.

    `legal_ground=6.1.f` documenta que el tratamiento se ampara en interés
    legítimo (LSSI-CE permite contacto B2B sobre datos profesionales).
    """
    enrichment = LeadEnrichment(
        lead_id=lead_id,
        source="google_maps",
        legal_ground="6.1.f",
        raw_payload={
            "place_id": place.place_id,
            "name": place.name,
            "formatted_address": place.formatted_address,
            "rating": place.rating,
            "user_ratings_total": place.user_ratings_total,
            "types": list(place.types),
        },
    )
    ctx.session.add(enrichment)


def _audit_discover(
    ctx: AgentContext, lead_id: int, query: str, place: PlaceResult
) -> None:
    ctx.session.add(
        AuditLog(
            actor="prospector",
            action=AuditAction.DISCOVER,
            entity_type="lead",
            entity_id=str(lead_id),
            legal_ground="6.1.f",
            payload={
                "query": query,
                "place_id": place.place_id,
                "source": "google_maps",
            },
        )
    )
