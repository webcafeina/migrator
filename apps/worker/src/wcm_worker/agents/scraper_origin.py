"""ScraperOriginAgent — crawl de la web origen del proyecto.

MVP: HTTP simple (httpx). Para webs con hidratación JS pesada (Wix/Webflow),
Fase 11 lo amplía con Playwright (depende del extra `[browser]` de
wcm_scraper_core).

Persiste cada página en `scraped_pages` con `html_raw`, `html_clean`,
estado y assets básicos referenciados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ScraperOriginError


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

        # BFS simple. Por seguridad: nunca seguimos links a otros dominios.
        to_visit: list[str] = [source_url]
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
                    scraped_at=datetime.now(timezone.utc),
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

    @staticmethod
    def _failed_page(project_id: int, url: str, error: str) -> ScrapedPage:
        return ScrapedPage(
            project_id=project_id,
            url=url,
            status=ScrapeStatus.FAILED,
            error_message=error[:500],
            scraped_at=datetime.now(timezone.utc),
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
