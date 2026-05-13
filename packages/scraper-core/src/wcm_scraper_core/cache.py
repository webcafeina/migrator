"""Cache backend abstracto para resultados de fetch + extracción.

Uso típico: cachear el HTML de una URL durante 7 días en prospección para
evitar refetcheo. En migración (web del cliente) no cachear.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol


class CacheBackend(Protocol):
    """Interfaz de cache. Implementaciones: InMemoryCache, RedisCache."""

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass
class _Entry:
    value: str
    expires_at: float


@dataclass
class InMemoryCache:
    """Cache en memoria con TTL. Para tests y dev sin Redis.

    Thread-safe? No. Si se usa desde múltiples threads, envolver en lock o
    cambiar a RedisCache.
    """

    _data: dict[str, _Entry] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._data[key]
            return None
        return entry.value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._data[key] = _Entry(value=value, expires_at=time.monotonic() + ttl_seconds)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
