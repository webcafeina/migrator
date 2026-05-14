"""Rate limiter por dominio.

Estrategia:
- Cada dominio tiene su propio "tiempo de siguiente request permitido".
- Entre requests al mismo dominio, espera aleatoria en `[min_delay, max_delay)`
  (jitter realista, no constante).
- Si un dominio devuelve 3 × {403,429,503} consecutivos en 24h, entra en
  cooldown 24h: cualquier request a ese dominio se rechaza con `DomainCooledDownError`.

El estado puede vivir en memoria (default, suficiente para un solo proceso)
o en Redis (Fase 6 cuando hay múltiples workers).
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from urllib.parse import urlparse


class DomainCooledDownError(RuntimeError):
    """Lanzado cuando se intenta acceder a un dominio en cooldown."""


def domain_of(url: str) -> str:
    """Extrae el dominio (host) de una URL. Lowercase."""
    return (urlparse(url).hostname or "").lower()


@dataclass
class _DomainState:
    next_allowed_at: float = 0.0
    block_count: int = 0
    first_block_at: float = 0.0
    cooled_until: float = 0.0


class DomainRateLimiter:
    """Rate limiter no-bloqueante por dominio.

    Usar con `async with limiter.acquire(url): ...`. El context manager espera
    el tiempo necesario antes de proceder. `report_blocked(url, status)` se
    llama tras recibir una respuesta para mantener contadores y cooldown.
    """

    def __init__(
        self,
        min_delay_s: float = 3.0,
        max_delay_s: float = 8.0,
        block_threshold: int = 3,
        block_window_s: float = 86400,
        cooldown_s: float = 86400,
        rng: random.Random | None = None,
        time_fn: object = None,
    ) -> None:
        if min_delay_s > max_delay_s:
            raise ValueError("min_delay_s no puede ser mayor que max_delay_s")
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        self.block_threshold = block_threshold
        self.block_window_s = block_window_s
        self.cooldown_s = cooldown_s
        self._rng = rng or random.Random()
        self._now = time_fn or time.monotonic
        self._state: dict[str, _DomainState] = {}

    def _state_for(self, domain: str) -> _DomainState:
        st = self._state.get(domain)
        if st is None:
            st = _DomainState()
            self._state[domain] = st
        return st

    def is_cooled_down(self, url_or_domain: str) -> bool:
        domain = url_or_domain if "/" not in url_or_domain else domain_of(url_or_domain)
        st = self._state.get(domain)
        return bool(st and self._now() < st.cooled_until)

    async def acquire(self, url: str) -> None:
        """Espera hasta que sea seguro hacer request al dominio.

        Lanza `DomainCooledDownError` si el dominio está en cooldown.
        """
        domain = domain_of(url)
        st = self._state_for(domain)
        now = self._now()

        if now < st.cooled_until:
            raise DomainCooledDownError(
                f"{domain} en cooldown hasta {st.cooled_until:.0f} (now={now:.0f})"
            )

        wait = st.next_allowed_at - now
        if wait > 0:
            await asyncio.sleep(wait)

        # Reservar la siguiente ventana con jitter
        delay = self._rng.uniform(self.min_delay_s, self.max_delay_s)
        st.next_allowed_at = self._now() + delay

    def report_blocked(self, url: str, status_code: int) -> None:
        """Registra una respuesta bloqueante (403/429/503).

        Si se acumulan `block_threshold` bloqueos dentro de `block_window_s`,
        el dominio entra en cooldown por `cooldown_s`.
        """
        if status_code not in (403, 429, 503):
            return
        domain = domain_of(url)
        st = self._state_for(domain)
        now = self._now()

        if now - st.first_block_at > self.block_window_s:
            # ventana caducada, reiniciar
            st.first_block_at = now
            st.block_count = 1
        else:
            st.block_count += 1

        if st.block_count >= self.block_threshold:
            st.cooled_until = now + self.cooldown_s

    def reset_cooldown(self, url_or_domain: str) -> None:
        """Para tests u operación manual: levanta cooldown."""
        domain = url_or_domain if "/" not in url_or_domain else domain_of(url_or_domain)
        if domain in self._state:
            self._state[domain] = _DomainState()
