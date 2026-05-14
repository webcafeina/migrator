"""Pool de User-Agents reales con rotación.

Dos modos:
- **Estático**: lista curada de UAs reales actualizada manualmente. Sin
  dependencias externas, funciona offline (tests, CI).
- **Dinámico (opcional)**: `fake-useragent` desde el paquete extra `[browser]`,
  que descarga UAs frescos de https://useragentstring.com periódicamente.

En producción se prefiere el dinámico; en desarrollo y tests el estático.
"""

from __future__ import annotations

import random
from collections.abc import Iterable

#: Lista curada actualizada manualmente (2026-05). Mezclas Chrome/Firefox/Safari
#: en Windows/macOS/Linux/Android/iOS. Mantener ~25 entradas reales.
STATIC_UA_POOL: tuple[str, ...] = (
    # Chrome desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Safari desktop
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    # Edge desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Chrome mobile (Android)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    # Safari mobile (iOS)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    # Brave / Chromium variantes
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Firefox ESR
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Ubuntu Chromium
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
)


class UserAgentPool:
    """Pool de User-Agents con rotación aleatoria.

    - `next()` devuelve un UA aleatorio.
    - `for_session(domain)` devuelve el mismo UA para un dominio durante la
      sesión actual (sticky), útil para crawls multi-página coherentes.
    """

    def __init__(
        self,
        pool: Iterable[str] | None = None,
        *,
        use_fake_useragent: bool = False,
        rng: random.Random | None = None,
    ) -> None:
        self._rng = rng or random.Random()
        self._sticky: dict[str, str] = {}

        if pool is not None:
            self._pool: tuple[str, ...] = tuple(pool)
        elif use_fake_useragent:
            try:
                from fake_useragent import UserAgent  # type: ignore[import-untyped]

                ua = UserAgent()
                # Mezcla por familia para diversidad
                items = [ua.chrome, ua.firefox, ua.safari, ua.edge]
                self._pool = tuple(items)
            except (ImportError, Exception):
                # Fallback silencioso al pool estático si fake-useragent falla
                self._pool = STATIC_UA_POOL
        else:
            self._pool = STATIC_UA_POOL

        if not self._pool:
            raise ValueError("UserAgentPool: pool vacío")

    def next(self) -> str:
        return self._rng.choice(self._pool)

    def for_session(self, sticky_key: str) -> str:
        if sticky_key not in self._sticky:
            self._sticky[sticky_key] = self.next()
        return self._sticky[sticky_key]

    def reset_session(self, sticky_key: str | None = None) -> None:
        if sticky_key is None:
            self._sticky.clear()
        else:
            self._sticky.pop(sticky_key, None)
