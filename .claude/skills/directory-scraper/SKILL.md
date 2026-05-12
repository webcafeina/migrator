---
name: directory-scraper
description: Lista mantenible de directorios sectoriales españoles y sus parsers (Páginas Amarillas, Empresite, axesor público, eInforma público, directorios sectoriales por nicho). Respeta robots.txt y rate-limits. Cumple cumplimiento legal.
---

# Skill — Directory Scraper

## Propósito

Descubrir empresas españolas a través de directorios públicos cuando Google Maps no basta (especialmente sectores B2B con perfil bajo en Maps).

## Directorios soportados (catálogo inicial)

| Directorio | URL base | Coberertura | Notas |
|---|---|---|---|
| Páginas Amarillas | `paginasamarillas.es` | General | Listado por categoría + provincia. Web > 200, anti-scraping agresivo. |
| Empresite | `empresite.eleconomista.es` | Por CIF, sector CNAE | Filtros avanzados. Algunos datos premium. |
| axesor público | `axesor.es` | Por CIF | Versión gratuita limitada. |
| eInforma público | `einforma.com` | Por CIF | Versión gratuita limitada a 5/día por IP. |
| ICEX directorio exportadores | `icex.es` | Empresas exportadoras | Sectoriales. |
| Confederaciones sectoriales | varios | Gremiales | Caso a caso (ej. CEHAT hostelería, CECE educación). |

## Contrato común

Cada parser implementa la misma interfaz:

```python
class DirectoryParser(Protocol):
    name: str
    base_url: str
    respects_robots: bool

    def search(
        self,
        sector: str,
        region: str,
        max_results: int = 100,
    ) -> Iterator[DirectoryEntry]:
        """Devuelve entries con: name, address, web?, phone?, source_url."""

    def is_blocked(self) -> bool:
        """True si Redis tiene la flag de cooldown 24h para esta fuente."""
```

## Reglas universales

1. **Respetar `robots.txt`**: parser comprueba antes de cualquier request. Si el directorio prohíbe, NO scrapear. Marcar en BD `directory.disabled_reason="robots_txt"`.
2. **Rate limit por dominio**: 1 req cada 5–10 s. Configurable por parser.
3. **Identificación**: User-Agent honesto: `Webcafeina-Migrator-Bot/<version> (+https://webcafeina.com/bot)`. Si el dominio bloquea, caer al pool de UAs reales (fake-useragent).
4. **Proxy**: aplicar `proxy-rotation` (residencial ES) salvo que el dominio detecte y prefiera tráfico directo (algunos directorios bloquean residenciales agresivamente).
5. **Caché**: 7 días por query (sector+región) en Redis.

## Estructura de parser

```python
class PaginasAmarillasParser(DirectoryParser):
    name = "paginas_amarillas"
    base_url = "https://www.paginasamarillas.es"
    respects_robots = True
    rate_limit_s = 8

    def search(self, sector, region, max_results=100):
        # 1. construir URL: /search/{sector_slug}/{region_slug}
        # 2. iterar páginas (paginación)
        # 3. parsear cada listing con BeautifulSoup
        # 4. yield DirectoryEntry
        ...
```

## Cumplimiento legal

- Solo datos públicos de empresa.
- Si un directorio expone datos personales de socios/administradores: filtrarlos, NO persistir.
- Cada `DirectoryEntry` se registra en `audit_log` con base jurídica interés legítimo + fuente concreta.

## Manejo de bloqueos

- HTTP 403 / 429: incrementar contador. 3 en 24h → marcar dominio como blocked por 24h.
- Captcha: si proxy-rotation no resuelve, **NO** ir a 2captcha (el coste no compensa para directorios "blandos"). Saltar al siguiente directorio.
- WAF Cloudflare interstitial: cambiar IP, si persiste, marcar blocked.

## Catálogo mantenible

Los parsers viven en `packages/scraper-core/directories/<name>.py`. Añadir uno nuevo:

1. Crear módulo en esa carpeta.
2. Implementar `DirectoryParser`.
3. Registrar en `packages/scraper-core/directories/__init__.py`.
4. Añadir tests con fixtures HTML reales (snapshot del listado real, anonimizado).
5. Documentar el directorio en esta tabla.

## Errores tipados

- `DirectoryScraperError` (raíz)
- `RobotsTxtForbiddenError`
- `ParserSchemaError` — el HTML cambió, selectores rotos (alerta para fix)
- `RateLimitError` (capturable, no fatal)
- `BlockedDirectoryError`

## Tests

- Fixtures HTML por directorio (`tests/fixtures/directories/<name>-<page>.html`)
- Test que el robots.txt se respeta
- Test de paginación

## Dependencias

- `requests` o `httpx`
- `beautifulsoup4`, `lxml`
- `urllib.robotparser` (stdlib)
- Redis
