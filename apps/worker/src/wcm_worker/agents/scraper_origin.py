"""ScraperOriginAgent — crawl de la web origen del proyecto.

MVP: HTTP simple (httpx). Para webs con hidratación JS pesada (Wix/Webflow),
Fase 11 lo amplía con Playwright (depende del extra `[browser]` de
wcm_scraper_core).

v0.18.0 — si `project.source_access_mode='api'` y el cliente nos dio
credenciales válidas del back (Wix REST v3 / Webflow API v2), el agente
sembra el BFS con la lista canónica de URLs devuelta por la API oficial.
Esto descubre páginas no enlazadas desde el menú público y suele dar
mejor cobertura. Si la API falla → cae al BFS tradicional sin romper.

Persiste cada página en `scraped_pages` con `html_raw`, `html_clean`,
estado y assets básicos referenciados.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ScraperOriginError
from wcm_worker.integrations.source_credentials import (
    CredentialsDecryptError,
    FernetNotConfiguredError,
    decrypt_source_credentials,
)
from wcm_worker.integrations.webflow_api import (
    WebflowApiClient,
    WebflowApiError,
)
from wcm_worker.integrations.wix_api import WixApiClient, WixApiError

log = logging.getLogger("wcm.worker.scraper_origin")


class ScraperOriginAgent(BaseAgent):
    name = "scraper-origin"
    phase_name = "scrape_origin"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise ScraperOriginError("ScraperOriginAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise ScraperOriginError(f"Project {ctx.project_id} no encontrado")

        max_pages = int(ctx.extra.get("max_pages", 50))
        source_url = project.source_url.rstrip("/")
        base_host = urlparse(source_url).netloc

        # v0.18.0 — Si el cliente nos dio credenciales del back, sembrar el
        # BFS con la lista canónica de URLs de la API oficial. Esto descubre
        # páginas que el menú público NO enlaza directamente (privacidad,
        # legal, landing pages sueltas). Si la API falla por cualquier motivo,
        # caemos al BFS tradicional desde source_url.
        seed_urls = self._seed_from_api(project)

        # BFS simple. Por seguridad: nunca seguimos links a otros dominios.
        to_visit: list[str] = [source_url, *seed_urls]
        visited: set[str] = set()
        results: list[ScrapedPage] = []

        with httpx.Client(timeout=20.0, follow_redirects=True, headers={
            "User-Agent": "WebcafeinaMigrator/0.1 (Authorized migration)"
        }) as client:
            while to_visit and len(results) < max_pages:
                url = to_visit.pop(0)
                if url in visited:
                    continue
                visited.add(url)

                try:
                    response = client.get(url)
                except httpx.RequestError as e:
                    results.append(self._failed_page(ctx.project_id, url, str(e)))
                    continue

                if response.status_code != 200:
                    results.append(self._failed_page(
                        ctx.project_id, url, f"HTTP {response.status_code}"
                    ))
                    continue

                soup = BeautifulSoup(response.text, "lxml")
                title_tag = soup.find("title")
                lang_tag = soup.find("html")

                page = ScrapedPage(
                    project_id=ctx.project_id,
                    url=url,
                    slug=self._url_to_slug(url, source_url),
                    title=(title_tag.string.strip() if title_tag and title_tag.string else None),
                    lang=(lang_tag.get("lang") if lang_tag and lang_tag.get("lang") else None),
                    depth=0,
                    html_raw=response.text,
                    html_clean=_sanitize_html(soup),
                    status=ScrapeStatus.SUCCESS,
                    scraped_at=datetime.now(UTC),
                )
                results.append(page)

                # Encontrar más links internos
                for a in soup.find_all("a", href=True):
                    candidate = urljoin(url, a["href"]).split("#")[0]
                    if urlparse(candidate).netloc == base_host and candidate not in visited:
                        to_visit.append(candidate)

        # Persistir
        ctx.session.add_all(results)
        ctx.session.flush()

        return AgentResult(
            summary=f"{project.source_url}: {len(results)} páginas scrapeadas",
            outputs={
                "scraped_pages": len(results),
                "successful": sum(1 for p in results if p.status == ScrapeStatus.SUCCESS),
                "failed": sum(1 for p in results if p.status == ScrapeStatus.FAILED),
            },
        )

    def _seed_from_api(self, project: Project) -> list[str]:
        """Si project.source_access_mode='api' y hay credenciales válidas,
        devuelve la lista de URLs canónicas según el adapter Wix/Webflow.
        Si algo falla → lista vacía + warning en log (cae al BFS tradicional)."""
        if project.source_access_mode != "api":
            return []
        if not project.source_credentials_encrypted:
            return []
        try:
            creds = decrypt_source_credentials(project.source_credentials_encrypted)
        except (FernetNotConfiguredError, CredentialsDecryptError) as e:
            log.warning(
                "scraper_origin_creds_decrypt_failed",
                extra={"project_id": project.id, "error": str(e)},
            )
            return []

        builder = (
            project.builder_source.value if project.builder_source else ""
        ).lower()
        try:
            return asyncio.run(self._fetch_api_urls(builder, creds))
        except (WixApiError, WebflowApiError) as e:
            log.warning(
                "scraper_origin_api_failed_fallback",
                extra={
                    "project_id": project.id,
                    "builder": builder,
                    "error": f"{type(e).__name__}: {e}",
                },
            )
            return []
        except Exception as e:  # noqa: BLE001 — cualquier excepción → fallback seguro
            log.warning(
                "scraper_origin_api_unexpected_error",
                extra={
                    "project_id": project.id,
                    "builder": builder,
                    "error": f"{type(e).__name__}: {e}",
                },
            )
            return []

    @staticmethod
    async def _fetch_api_urls(builder: str, creds: dict) -> list[str]:
        """Llama al adapter correspondiente. Devuelve URLs limpias."""
        if builder == "wix":
            async with WixApiClient(
                api_key=creds["api_key"], site_id=creds["site_id"]
            ) as client:
                pages = await client.list_page_urls()
                return [p.url for p in pages if p.url]
        if builder == "webflow":
            async with WebflowApiClient(
                api_token=creds["api_token"], site_id=creds["site_id"]
            ) as client:
                pages = await client.list_page_urls()
                return [p.url for p in pages if p.url]
        return []

    @staticmethod
    def _failed_page(project_id: int, url: str, error: str) -> ScrapedPage:
        return ScrapedPage(
            project_id=project_id,
            url=url,
            status=ScrapeStatus.FAILED,
            error_message=error[:500],
            scraped_at=datetime.now(UTC),
        )

    @staticmethod
    def _url_to_slug(url: str, base_url: str) -> str:
        path = url.removeprefix(base_url).strip("/")
        return path or "home"


def _sanitize_html(soup: BeautifulSoup) -> str:
    """Sanitización ligera: eliminar scripts, tracking, comments."""
    for tag in soup.find_all(["script", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"data-wix-bi": True}):
        tag.decompose()
    return str(soup)
