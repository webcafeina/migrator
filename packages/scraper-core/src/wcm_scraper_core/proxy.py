"""Proxy rotator con estrategia layered free→paid (ADR-017).

Selecciona automáticamente backend según env vars presentes:
1. `WEBSHARE_API_TOKEN` → WebshareBackend (10 datacenter free + 1GB/mes)
2. `SCRAPERAPI_KEY` → ScraperApiBackend (5k calls/mes free + captcha handling)
3. `BRIGHTDATA_PASSWORD` (+ CUSTOMER_ID, ZONE) → BrightDataBackend (paid premium)
4. Default → NoProxyBackend (acceso directo, dev y migración cliente)

Si el backend activo falla 3×403/429 sobre un dominio, el rate-limiter pone
ese dominio en cooldown 24h; opcionalmente, si hay un backend de mayor tier
disponible, el rotator escala. La lógica de escalado se aplica en `scraper-origin`
agente y no aquí (separación de capas).
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class ProxyConfig:
    """Configuración de un proxy listo para usar con httpx/requests/Playwright.

    `url` formato: scheme://[user:pass@]host:port
    """

    url: str
    label: str  # backend name + opcional country/session
    sticky_key: str | None = None  # si se solicitó sticky session


class ProxyBackend(Protocol):
    """Interfaz que cumple cada backend (Webshare, ScraperAPI, Bright Data, etc.)."""

    name: str

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None: ...

    def is_available(self) -> bool: ...


# ---------- Backends ----------


class NoProxyBackend:
    """Backend nulo: usa la IP directa del proceso. Default en dev y en
    migración cliente (donde no se debe enmascarar la identidad)."""

    name = "noproxy"

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        return None

    def is_available(self) -> bool:
        return True


@dataclass
class WebshareBackend:
    """10 datacenter proxies free, sin tarjeta, sin caducar.

    Setup:
    1. Crear cuenta en webshare.io (free).
    2. Copiar API token (Proxy Settings → API).
    3. Endpoint rotating (no necesita listar IPs): proxy.webshare.io:80
       con auth basic <user>:<pass>.

    En el free plan se rota automáticamente entre las 10 IPs disponibles.
    """

    name = "webshare"
    username: str
    password: str
    endpoint_host: str = "p.webshare.io"
    endpoint_port: int = 80
    _rng: random.Random = field(default_factory=random.Random)

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        # Webshare rotating endpoint: la rotación la hace el servidor.
        # Para sticky session se usa el flag -<n> en el username (1..10).
        user = self.username
        if sticky_key:
            slot = (hash(sticky_key) % 10) + 1
            user = f"{self.username}-{slot}"
        url = f"http://{user}:{self.password}@{self.endpoint_host}:{self.endpoint_port}"
        return ProxyConfig(url=url, label="webshare", sticky_key=sticky_key)

    def is_available(self) -> bool:
        return bool(self.username and self.password)


@dataclass
class ScraperApiBackend:
    """5k calls/mes free, maneja rotación + captcha + JS rendering.

    Setup: crear cuenta scraperapi.com → copiar API key.

    Modo de operación: en lugar de "proxy", ScraperAPI envuelve la URL:
        GET http://api.scraperapi.com?api_key=KEY&url=<target>
    Aquí lo modelamos como un proxy HTTP `proxy-server.scraperapi.com:8001`
    con auth basic `scraperapi:KEY` (modo proxy oficial).
    """

    name = "scraperapi"
    api_key: str
    endpoint_host: str = "proxy-server.scraperapi.com"
    endpoint_port: int = 8001

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        username = "scraperapi"
        if sticky_key:
            username = f"scraperapi.session_number={abs(hash(sticky_key)) % 100000}"
        url = f"http://{username}:{self.api_key}@{self.endpoint_host}:{self.endpoint_port}"
        return ProxyConfig(url=url, label="scraperapi", sticky_key=sticky_key)

    def is_available(self) -> bool:
        return bool(self.api_key)


@dataclass
class BrightDataBackend:
    """Bright Data residencial — premium, pay-as-you-go.

    Mantenido como opción para volumen alto. Activar cuando los free tiers
    se queden cortos.
    """

    name = "brightdata"
    customer_id: str
    zone: str
    password: str
    host: str = "brd.superproxy.io"
    port: int = 22225

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        user = f"{self.customer_id}-zone-{self.zone}"
        if sticky_key:
            user = f"{user}-session-{abs(hash(sticky_key)) % 1_000_000}"
        url = f"http://{user}:{self.password}@{self.host}:{self.port}"
        return ProxyConfig(url=url, label="brightdata", sticky_key=sticky_key)

    def is_available(self) -> bool:
        return bool(self.customer_id and self.zone and self.password)


# ---------- Rotator ----------


@dataclass
class ProxyRotator:
    """Rota entre backends según disponibilidad y prioridad.

    Por defecto se construye con `build_default_rotator()` que lee env vars.
    El método `current_backend()` devuelve el primer backend disponible
    según prioridad. `next_proxy()` delega en el backend activo.

    El escalado free→paid se decide externamente (scraper-origin agente);
    aquí mantenemos la elección estable hasta que se cambie `active_index`.
    """

    backends: list[ProxyBackend]
    active_index: int = 0

    def current_backend(self) -> ProxyBackend:
        return self.backends[self.active_index]

    def next_proxy(self, sticky_key: str | None = None) -> ProxyConfig | None:
        backend = self.current_backend()
        if not backend.is_available():
            # Backend marcado pero no realmente disponible: cae al siguiente.
            for i in range(len(self.backends)):
                if self.backends[i].is_available():
                    self.active_index = i
                    backend = self.backends[i]
                    break
        return backend.next_proxy(sticky_key=sticky_key)

    def escalate(self) -> bool:
        """Pasa al siguiente backend disponible. Devuelve True si escaló."""
        for i in range(self.active_index + 1, len(self.backends)):
            if self.backends[i].is_available():
                self.active_index = i
                return True
        return False

    def iter_available(self) -> Iterator[ProxyBackend]:
        for b in self.backends:
            if b.is_available():
                yield b


def build_default_rotator(env: dict[str, str] | None = None) -> ProxyRotator:
    """Construye el rotator leyendo env vars en orden de prioridad creciente
    (paid wins si está configurado, pero los free pueden ser default
    explícitamente eligiendo `active_index`).

    Orden de backends devuelto: [NoProxy, Webshare, ScraperAPI, BrightData].
    `active_index` arranca en el primer disponible distinto de NoProxy si
    el modo es producción; en dev se queda en NoProxy.
    """
    e = env if env is not None else os.environ

    backends: list[ProxyBackend] = [NoProxyBackend()]

    if e.get("WEBSHARE_API_TOKEN") or (e.get("WEBSHARE_USER") and e.get("WEBSHARE_PASSWORD")):
        backends.append(
            WebshareBackend(
                username=e.get("WEBSHARE_USER", e.get("WEBSHARE_API_TOKEN", "")),
                password=e.get("WEBSHARE_PASSWORD", ""),
            )
        )

    if e.get("SCRAPERAPI_KEY"):
        backends.append(ScraperApiBackend(api_key=e["SCRAPERAPI_KEY"]))

    if e.get("BRIGHTDATA_PASSWORD") and e.get("BRIGHTDATA_CUSTOMER_ID") and e.get("BRIGHTDATA_ZONE"):
        backends.append(
            BrightDataBackend(
                customer_id=e["BRIGHTDATA_CUSTOMER_ID"],
                zone=e["BRIGHTDATA_ZONE"],
                password=e["BRIGHTDATA_PASSWORD"],
                host=e.get("BRIGHTDATA_PROXY_HOST", "brd.superproxy.io"),
                port=int(e.get("BRIGHTDATA_PROXY_PORT", "22225")),
            )
        )

    env_mode = (e.get("ENV") or "development").lower()
    if env_mode in {"production", "staging"} and len(backends) > 1:
        # Empezar con el primer paid/free disponible
        active = 1
    else:
        active = 0

    return ProxyRotator(backends=backends, active_index=active)
