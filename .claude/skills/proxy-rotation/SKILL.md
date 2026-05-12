---
name: proxy-rotation
description: Uso de Bright Data residencial con rotación automática + cooldown por dominio si HTTP 429/403. Configuración por entorno (dev sin proxy, staging mock, producción residencial). En migración de webs del cliente NO usar proxy.
---

# Skill — Proxy Rotation

## Propósito

Hacer fingerprinting y scraping prospectivo sin que las fuentes nos bloqueen. Solo aplica en **prospección** (no en migración).

## Cuándo aplicar

- Operación = prospección (descubrimiento, fingerprint masivo, enrichment).
- NO aplicar en migración (scraping autorizado de web del cliente).
- NO aplicar contra APIs oficiales (Google Places, ClickUp, Resend, etc.).

## Configuración por entorno

| Env | Estrategia |
|---|---|
| `development` | Sin proxy (peticiones directas). Cuidado: si se hace bulk testing real, activar manualmente. |
| `staging` | Proxy Bright Data en modo "datacenter" (más barato) para pruebas. |
| `production` | Proxy Bright Data residencial con rotación por request. |

## Contrato

```python
class ProxyRotator:
    def __init__(self, env: str = "production"):
        self.session_factory = self._build_session_factory()

    def get_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        """Devuelve config de proxy. Si sticky_key, usa misma IP por sesión (útil para multi-step en una web)."""

    def report_block(self, domain: str, status_code: int) -> None:
        """Registra 403/429. Si 3 en 24h, cooldown del dominio."""

    def is_domain_cooled_down(self, domain: str) -> bool: ...

    def reset_cooldown(self, domain: str) -> None: ...
```

## Estrategia de rotación

- **Por defecto**: una IP distinta por request.
- **Sticky session**: cuando un crawl multi-página requiere consistencia (sitios que comprueban sesión coherente), usar `sticky_key=<domain>` por hasta 10 min.
- **Geo-targeting**: por defecto España (Bright Data permite filtrar `country=ES`). Para fuentes que tratan distinto a IPs ES (poco común), usar otros.

## Cooldown por dominio

Estado en Redis: `proxy:cooldown:<domain>` con TTL 24h.

```python
def cooldown_logic(domain, status):
    if status in (429, 403):
        count = redis.incr(f"proxy:blocks:{domain}")
        redis.expire(f"proxy:blocks:{domain}", 86400)
        if count >= 3:
            redis.set(f"proxy:cooldown:{domain}", "1", ex=86400)
            log.warning("domain_cooled_down", domain=domain)
```

## Rate limiting

Independiente de proxy: ya hace lo suyo `scraper-core` con jitter 3–8 s. Proxy no exime de respetar tasa.

## Detección de bloqueo

- HTTP 403, 429, 503 → contar como bloqueo
- HTML con texto "captcha", "verifying you are human", "blocked" → bloqueo (incluso si status 200)
- Cloudflare "Just a moment..." page → bloqueo, intentar siguiente IP

## Bright Data config

Vía SDK oficial (`brightdata` package):

```python
proxy_url = f"http://{CUSTOMER_ID}-zone-{ZONE}:{PASSWORD}@{HOST}:{PORT}"
session.proxies = {"http": proxy_url, "https": proxy_url}
```

Para sticky session, añadir `-session-{key}` al usuario:
```
http://{CUSTOMER_ID}-zone-{ZONE}-session-{key}:...
```

## Coste

- Bright Data residencial es **pay-as-you-go** por GB transferido.
- Optimizaciones:
  - Habilitar GZIP / Brotli (`Accept-Encoding: gzip, br`)
  - Streaming si el archivo es grande
  - Solo cargar HTML (no assets) salvo en `scraper-origin` que sí necesita CSS computado
- Reporte mensual en dashboard: GB consumidos por proyecto / campaña.

## Tests

- Mock de Bright Data en tests unit
- Test cooldown: 3 bloqueos → set cooldown; comprobar
- Test sticky session: misma key → misma IP en simulación

## Dependencias

- `requests` o `httpx`
- Credenciales en `.env`: `BRIGHTDATA_CUSTOMER_ID`, `BRIGHTDATA_ZONE`, `BRIGHTDATA_PASSWORD`, `BRIGHTDATA_PROXY_HOST`, `BRIGHTDATA_PROXY_PORT`

## Cuándo NO usar este skill

- Migración del cliente (scraping autorizado, IP directa Webcafeína)
- APIs oficiales con auth (Google Maps, ClickUp, Resend)
- Tests automáticos contra mocks
