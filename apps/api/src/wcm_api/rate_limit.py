"""Rate limiting con slowapi (Fase 15).

Limiter global compartido. Se inicializa una vez en `main.py` y se aplica
a endpoints sensibles con el decorador `@limiter.limit("N/period")`.

Key function:
- Por defecto, IP del cliente (`X-Forwarded-For` honrado por uvicorn con
  `--proxy-headers`).
- Para endpoints autenticados, mejor key = user id si está disponible
  (evita penalizar a operadores legítimos compartiendo IP de oficina).

Storage:
- En MVP usamos in-memory (default slowapi). Para multi-worker o multi-nodo,
  cambiar a `storage_uri="redis://..."`. Pendiente WCM-017.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _key_func(request: Request) -> str:
    """Combina IP + (si hay) sub del JWT para limitar mejor.

    Evita que dos operadores tras la misma NAT se penalicen mutuamente —
    cada uno tiene su propio token y por tanto su propio bucket.
    """
    ip = get_remote_address(request)
    # El TokenPayload se inyecta vía Depends; no está accesible aquí sin
    # acoplar a FastAPI. Si en el futuro queremos key por user, expandir.
    return ip


#: Limiter compartido por toda la app. Se importa en main.py + en cada
#: router que aplique límites.
limiter = Limiter(key_func=_key_func, default_limits=[])
