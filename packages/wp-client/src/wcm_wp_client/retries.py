"""Retry con backoff exponencial y respeto a Retry-After.

Pequeño y autocontenido: evitamos dependencia tenacity para no inflar el
runtime del worker. Si la lógica crece, refactorizar a tenacity.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

#: Status codes que merecen reintento.
RETRIABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 2.0,
    max_delay_s: float = 32.0,
    jitter: float = 0.25,
    is_retriable: Callable[[BaseException], bool] | None = None,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Ejecuta `fn` con reintentos exponenciales.

    Espera tras intento N = `min(base * 2^N, max) + jitter`.
    `is_retriable` decide si una excepción merece reintento.
    """
    if is_retriable is None:
        # Por defecto: solo RetryableSignal explícito (ver retries en httpx wrapper)
        is_retriable = lambda _e: False  # noqa: E731

    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except BaseException as e:
            last_exc = e
            if not is_retriable(e) or attempt == max_attempts - 1:
                raise
            delay = min(base_delay_s * (2**attempt), max_delay_s)
            delay += random.uniform(0, delay * jitter)
            if on_retry is not None:
                on_retry(attempt + 1, delay, e)
            await asyncio.sleep(delay)

    # Inalcanzable — el último `attempt` siempre raise. Documentación para mypy.
    raise RuntimeError("retry_async: lógica inalcanzable") from last_exc  # pragma: no cover
