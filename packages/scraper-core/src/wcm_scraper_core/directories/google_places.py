"""Cliente Google Places API (legacy).

ADR-024: usamos la API legacy (`maps.googleapis.com/maps/api/place/*`)
porque la API key del proyecto solo tiene habilitada esta versión. Si
en el futuro se migra a Places API (New), reescribir este módulo —
el contrato `GooglePlacesClient` se mantiene estable.

Operaciones:
- `text_search(query, region)` → enumera lugares por texto libre
  (ej. "restaurantes en Cáceres").
- `place_details(place_id)` → trae website, teléfono, dirección
  formateada y rating.

Diseño:
- HTTP a través de httpx con timeout estricto.
- Cache con TTL de 7 días (cache key = endpoint + sorted params hash).
  Las webs de PYMEs cambian raramente; 7d es buen compromiso entre
  freshness y coste de quota.
- Field mask reducido en details: solo lo necesario para prospección.
- Retry exponencial sobre 429/503. Sobre 403/INVALID_REQUEST no
  reintenta — son errores definitivos.
- Lazy paginación: `text_search` devuelve generator, no lista; el
  consumidor decide cuántas páginas pide (cada página = 20 resultados,
  máx 60 por query según Google).

Cuotas (estado mayo 2026, sujeto a cambio):
- Text Search: 60 calls/min, $32/1000 (los primeros 200/mes gratis con
  $200 crédito mensual).
- Place Details (Basic): $17/1000.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlencode

import httpx

from wcm_scraper_core.cache import CacheBackend, InMemoryCache

log = logging.getLogger("wcm.scraper.google_places")

#: Base de la API legacy (Places API v3, "the old one").
DEFAULT_BASE = "https://maps.googleapis.com/maps/api/place"

#: TTL del cache. 7 días balancea quota vs freshness para webs de PYMEs.
DEFAULT_CACHE_TTL_S = 7 * 24 * 3600

#: Fields mínimos en place_details. Cada field cuesta tier distinto;
#: Basic Data es lo más barato y cubre todo lo que prospección necesita.
DETAIL_FIELDS = (
    "place_id,name,formatted_address,website,international_phone_number,"
    "url,rating,user_ratings_total,types,address_components"
)


class GooglePlacesError(Exception):
    """Error genérico de la API. Argumentos: (status, message)."""

    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message
        super().__init__(f"GooglePlaces[{status}]: {message}" if message else f"GooglePlaces[{status}]")


class GooglePlacesQuotaExceeded(GooglePlacesError):
    """Quota diaria/minuto alcanzada — el caller debería pausar o degradar."""


@dataclass(frozen=True)
class PlaceResult:
    """Normalizado del resultado de text_search o place_details.

    Mantiene `raw` por si el caller necesita datos no proyectados.
    """

    place_id: str
    name: str
    formatted_address: str | None
    website: str | None
    phone: str | None
    rating: float | None
    user_ratings_total: int | None
    types: tuple[str, ...] = field(default_factory=tuple)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_website(self) -> bool:
        return bool(self.website)


class GooglePlacesClient:
    """Cliente sincrónico. Para uso desde Celery workers.

    Usage:
        client = GooglePlacesClient(api_key="...")
        for place in client.text_search("agencia marketing en Madrid", max_pages=3):
            details = client.place_details(place.place_id)
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE,
        language: str = "es",
        region: str = "es",
        cache: CacheBackend | None = None,
        cache_ttl_s: int = DEFAULT_CACHE_TTL_S,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        retry_base_delay_s: float = 1.0,
    ) -> None:
        if not api_key:
            raise GooglePlacesError("MISSING_API_KEY", "GOOGLE_MAPS_API_KEY vacía")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.region = region
        self.cache: CacheBackend = cache or InMemoryCache()
        self.cache_ttl_s = cache_ttl_s
        self._http = http_client or httpx.Client(timeout=15.0, follow_redirects=False)
        self._owns_http = http_client is None
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "GooglePlacesClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------- public ----------

    def text_search(
        self,
        query: str,
        *,
        max_pages: int = 1,
        radius_m: int | None = None,
        location: tuple[float, float] | None = None,
    ) -> Iterator[PlaceResult]:
        """Itera resultados de Text Search.

        Google sirve 20 resultados/página, máximo 60 (3 páginas) por query.
        `max_pages` limita la profundidad para controlar quota.

        Si `location` y `radius_m` se proporcionan, restringe el área.
        """
        next_token: str | None = None
        for page_idx in range(max_pages):
            params: dict[str, str | int | float] = {
                "query": query,
                "language": self.language,
                "region": self.region,
            }
            if next_token:
                # Google requiere ~2s antes de que un next_page_token sea
                # válido. Pausa defensiva.
                time.sleep(2.0)
                params["pagetoken"] = next_token
            else:
                if location is not None:
                    params["location"] = f"{location[0]},{location[1]}"
                if radius_m is not None:
                    params["radius"] = radius_m

            data = self._get("/textsearch/json", params)
            for raw in data.get("results", []):
                yield _parse_text_search_result(raw)

            next_token = data.get("next_page_token")
            if not next_token:
                break

    def place_details(self, place_id: str) -> PlaceResult | None:
        """Detalles de un place_id concreto.

        Devuelve `None` si Google responde NOT_FOUND (lugar borrado del
        índice). Para el resto de errores lanza GooglePlacesError.
        """
        params = {
            "place_id": place_id,
            "fields": DETAIL_FIELDS,
            "language": self.language,
        }
        try:
            data = self._get("/details/json", params)
        except GooglePlacesError as e:
            if e.status == "NOT_FOUND":
                return None
            raise
        result = data.get("result")
        if not result:
            return None
        return _parse_text_search_result(result)

    # ---------- internals ----------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET con cache + retries. Lanza GooglePlacesError en errores
        definitivos. Quota → GooglePlacesQuotaExceeded.
        """
        cache_key = _cache_key(path, params)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        params_with_key = {**params, "key": self.api_key}
        url = f"{self.base_url}{path}"

        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._http.get(url, params=params_with_key)
            except httpx.RequestError as e:
                if attempt >= self.max_retries:
                    raise GooglePlacesError("NETWORK", str(e)) from e
                _sleep_backoff(attempt, self.retry_base_delay_s)
                continue

            if resp.status_code in (429, 503):
                if attempt >= self.max_retries:
                    raise GooglePlacesQuotaExceeded(
                        "HTTP_" + str(resp.status_code), resp.text[:200]
                    )
                _sleep_backoff(attempt, self.retry_base_delay_s)
                continue
            if resp.status_code != 200:
                raise GooglePlacesError(
                    "HTTP_" + str(resp.status_code), resp.text[:500]
                )

            data = resp.json()
            status = data.get("status", "UNKNOWN")
            if status in ("OK", "ZERO_RESULTS"):
                # Solo cacheamos respuestas válidas. ZERO_RESULTS también
                # se cachea: ahorra una llamada idéntica los próximos 7 días.
                self.cache.set(cache_key, json.dumps(data), self.cache_ttl_s)
                return data
            if status in ("OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT"):
                raise GooglePlacesQuotaExceeded(status, data.get("error_message", ""))
            if status == "REQUEST_DENIED":
                # API key inválida / sin permisos / facturación off.
                # NO retry — es un error definitivo de configuración.
                raise GooglePlacesError(status, data.get("error_message", ""))
            if status == "NOT_FOUND":
                raise GooglePlacesError(status, data.get("error_message", ""))
            # INVALID_REQUEST u otros → reintenta una vez por si es transitorio.
            if attempt >= self.max_retries:
                raise GooglePlacesError(status, data.get("error_message", ""))
            _sleep_backoff(attempt, self.retry_base_delay_s)


def _parse_text_search_result(raw: dict[str, Any]) -> PlaceResult:
    """Normaliza un resultado de la API a `PlaceResult`. Permisivo con
    campos ausentes — la API legacy a veces los omite sin avisar.
    """
    phone = raw.get("international_phone_number") or raw.get("formatted_phone_number")
    return PlaceResult(
        place_id=raw.get("place_id", ""),
        name=raw.get("name", ""),
        formatted_address=raw.get("formatted_address"),
        website=raw.get("website"),
        phone=phone,
        rating=raw.get("rating"),
        user_ratings_total=raw.get("user_ratings_total"),
        types=tuple(raw.get("types", []) or []),
        raw=raw,
    )


def _cache_key(path: str, params: dict[str, Any]) -> str:
    """Cache key estable: path + params ordenados + sha256 corto.

    NO incluye la api_key (sería una fuga al log si se imprime el key).
    """
    sanitized = {k: v for k, v in params.items() if k != "key"}
    blob = path + "?" + urlencode(sorted(sanitized.items()))
    return "gp:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _sleep_backoff(attempt: int, base: float) -> None:
    """Exponential backoff 1s → 2s → 4s ..."""
    time.sleep(base * (2 ** (attempt - 1)))
