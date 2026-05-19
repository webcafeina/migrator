"""Verificador de links del dominio destino (v0.16.0).

Extrae `<a href>` de cada página renderizada del WP destino y
comprueba que cada URL responde 2xx/3xx. Solo verifica URLs del MISMO
dominio (los externos quedan documentados como residual si interesa).

Estrategia:
1. Para cada `ScrapedPage` del proyecto, calcula `target_url` =
   `target_domain + path`.
2. Fetch del HTML renderizado del destino (httpx).
3. Parse con BeautifulSoup para extraer hrefs.
4. Filtra solo links del mismo dominio + dedupe global.
5. HEAD a cada URL única (timeout 10s, follow_redirects=True).
6. Report agregado: total_checked, broken (4xx/5xx + timeouts).

Decisión: HEAD primero por velocidad. Si HEAD devuelve 405 (Method
Not Allowed — pasa con WP REST), fallback a GET con `Range: bytes=0-1023`
para no descargar todo el body.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("wcm.worker.integrations.link_checker")

DEFAULT_TIMEOUT_S = 10
DEFAULT_CONCURRENT_LIMIT = 5  # Conservador para no DDoSearnos a nosotros mismos.


@dataclass(frozen=True)
class BrokenLink:
    """Un link roto detectado."""

    url: str
    status_code: int | None
    error: str | None = None
    """Solo si la request falló (timeout, DNS, etc). Si llegó respuesta, status_code."""
    source_pages: tuple[str, ...] = ()
    """Pages donde aparece este link (para ayudar al operador a localizar)."""


@dataclass
class LinkReport:
    """Resumen de comprobación de links."""

    total_checked: int = 0
    broken_count: int = 0
    broken: list[BrokenLink] = field(default_factory=list)


def check_links(
    page_urls: Iterable[str],
    *,
    target_host: str,
    http_client: httpx.Client | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> LinkReport:
    """Para cada URL de page renderiza el HTML, extrae links, comprueba
    estados. Solo verifica links del mismo `target_host`.

    `page_urls` son las URLs en el destino (ej. `https://migrator.test/contacto`).
    """
    client = http_client or httpx.Client(timeout=timeout_s, follow_redirects=True, verify=False)
    own_client = http_client is None
    try:
        # 1. Collect: link → set de páginas donde aparece.
        link_sources: dict[str, set[str]] = {}
        for page_url in page_urls:
            try:
                resp = client.get(page_url)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                log.warning(
                    "link_checker_fetch_page_failed", extra={"url": page_url, "error": str(e)}
                )
                continue
            if resp.status_code >= 400:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = str(a["href"]).strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                absolute = urljoin(page_url, href)
                parsed = urlparse(absolute)
                if parsed.hostname is None:
                    continue
                if parsed.hostname.lower() != target_host.lower():
                    continue
                # Normaliza: drop fragment.
                normalized = absolute.split("#", 1)[0]
                link_sources.setdefault(normalized, set()).add(page_url)

        # 2. Check: HEAD primero, GET ranged como fallback.
        report = LinkReport()
        for link, sources in link_sources.items():
            report.total_checked += 1
            broken = _check_one(client, link, list(sources))
            if broken:
                report.broken.append(broken)
                report.broken_count += 1
        return report
    finally:
        if own_client:
            client.close()


def _check_one(client: httpx.Client, url: str, sources: list[str]) -> BrokenLink | None:
    """HEAD primero. Si 405 (algunos servers no soportan HEAD), fallback
    a GET con Range. Si la response es <400, devuelve None (no broken).
    """
    try:
        resp = client.head(url)
        if resp.status_code == 405:
            resp = client.get(url, headers={"Range": "bytes=0-1023"})
        if resp.status_code < 400:
            return None
        return BrokenLink(url=url, status_code=resp.status_code, source_pages=tuple(sources))
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        return BrokenLink(
            url=url,
            status_code=None,
            error=f"{type(e).__name__}: {str(e)[:120]}",
            source_pages=tuple(sources),
        )
