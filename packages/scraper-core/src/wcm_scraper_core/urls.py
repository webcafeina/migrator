"""Canonicalización de URLs para deduplicación de leads.

Doble caller: ProspectorAgent (descubrimiento automático) y el endpoint
`POST /api/v1/leads` (alta manual). Ambos deben aplicar la MISMA
canonicalización para que el `UNIQUE(url)` de la tabla `leads` no
genere duplicados accidentales por diferencias triviales (www, trailing
slash, querystring de tracking, fragment).
"""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_lead_url(url: str) -> str:
    """Canónica determinista: scheme + host sin www + path sin trailing slash.

    Reglas (sí se aplica):
    - Lower-case del host.
    - Strip `www.` del host.
    - `https` por defecto si la URL no trae scheme.
    - Path sin trailing slash; vacío → `/`.
    - **Querystring SIEMPRE descartado** — evita duplicados por UTMs
      (`utm_source`, `fbclid`, `gclid`, etc.). Decisión documentada en
      ADR/release v0.11.0.
    - **Fragment SIEMPRE descartado** — los fragments son cliente,
      irrelevantes para identificar la web.

    No se aplica (limitaciones conocidas):
    - Puertos explícitos (`:443`, `:80`) NO se normalizan; `foo.com:443`
      sigue distinto de `foo.com`. Caso raro en URLs comerciales.
    - IDN/punycode: respetamos lo que devuelve `urlparse.hostname` (que
      ya hace lower-case ASCII).
    """
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{host}{path}"
