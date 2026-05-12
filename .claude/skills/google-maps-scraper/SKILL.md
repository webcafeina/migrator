---
name: google-maps-scraper
description: Descubrimiento de empresas españolas vía Google Maps Places API (oficial, no scraping). Búsqueda por sector + región. Respeta cuotas, cachea 7 días, devuelve nombre, dirección, web, teléfono, place_id. Fuente principal de prospector.
---

# Skill — Google Maps Scraper

## Propósito

Usar la API oficial de Google Places para descubrir empresas candidatas a leads. **API oficial, no scraping**. Cumple ToS y es la fuente más fiable.

## Contrato

```python
class GoogleMapsClient:
    def __init__(self, api_key: str):
        ...

    def find_places(
        self,
        query: str,                # "restaurantes en Sevilla"
        location: str | None = None,  # lat,lng,radius_m si quieres restringir geográficamente
        max_results: int = 100,
        cache_ttl_seconds: int = 604800,  # 7 días
    ) -> list[PlaceSummary]:
        """Devuelve summary list. Cada item es 1 unidad de cuota Text Search."""

    def get_place_details(self, place_id: str) -> PlaceDetails:
        """Detalle con web, teléfono, horarios, reseñas. 1 unidad cuota Details."""
```

## Endpoints utilizados

1. **Text Search** (`/place/textsearch/json`) — descubrimiento por query libre
2. **Place Details** (`/place/details/json`) — solo si necesitamos campos premium (web, teléfono)

**Importante**: en Place Details, especificar `fields=` para no pagar campos que no usamos. Solo pedir:
- `website`
- `formatted_address`
- `international_phone_number`
- `name`
- `place_id`
- `types`
- `business_status`

## Mapping query → sector + región

`prospector` traduce:
```python
def build_query(sector: str, region: str) -> str:
    # Sector EN inglés a menudo da más resultados en Maps
    sector_map = {
        "restauración": "restaurantes",
        "clínica dental": "clínicas dentales",
        "asesoría fiscal": "asesorías fiscales",
        ...
    }
    return f"{sector_map.get(sector, sector)} en {region}"
```

## Paginación

- Text Search devuelve max 20 resultados por página, hasta 3 páginas (60 total).
- Para más, segmentar por sub-región (provincia → ciudad → barrio).

## Cuotas y coste

- **Free tier**: $200/mes en créditos.
- Text Search: $32 / 1000 calls = $0.032 por call.
- Place Details (con field mask reducido): $17 / 1000 calls.
- Para 50 leads enriquecidos: ~ 50 × 0.032 + 50 × 0.017 = ~ $2.45.

## Cache

- Key: `gmaps:<sha256(query+location)>`
- TTL: 7 días por defecto
- Cache de Place Details con TTL más largo (30 días, los datos cambian poco)

## Filtrado post-búsqueda

Aplicar:
- `business_status == "OPERATIONAL"` (descartar cerradas / movidas)
- `website` presente (sin web no nos sirve para fingerprint posterior)
- Dominio NO en blacklist (clientes existentes, competidores, listado interno)

## Errores tipados

- `GoogleMapsError` (raíz)
- `QuotaExceededError`
- `InvalidApiKeyError`
- `ZeroResultsError` — no es error real pero merece registro para ajustar query

## Tests

- Mock de Google API
- Test cache: 2 calls con mismo query → 1 hit API + 1 hit cache

## Dependencias

- `googlemaps` SDK Python oficial
- Redis para cache
- Credenciales: `GOOGLE_MAPS_API_KEY`
