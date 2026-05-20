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
import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import (
    ResidualCategory,
    ResidualStatus,
    ScrapeStatus,
)
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

        # Idempotencia: si el agent se re-ejecuta (force_rerun_all, restart,
        # rollback+retry) hay que borrar las scraped_pages previas o el
        # constraint UNIQUE(project_id, url) levantará IntegrityError al
        # hacer flush. Hacemos limpieza completa para que el resultado sea
        # determinista (no mezcla de runs).
        from sqlalchemy import delete
        ctx.session.execute(
            delete(ScrapedPage).where(ScrapedPage.project_id == ctx.project_id)
        )
        ctx.session.flush()

        # ADR-050 — cascada: project.max_pages_scrape > env SCRAPE_MAX_PAGES_DEFAULT > 50.
        max_pages = self._resolve_max_pages(project, ctx)
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

        # ADR-040 — Playwright cuando esté disponible para builders SPA
        # (Wix/Webflow) o si SCRAPE_USE_PLAYWRIGHT=true. Fallback httpx.
        use_pw = self._should_use_playwright(project)
        fetcher_cm: Any
        if use_pw:
            from wcm_worker.integrations.playwright_fetcher import (
                PlaywrightNotAvailableError,
                fetcher_session,
            )
            try:
                fetcher_cm = fetcher_session()
            except PlaywrightNotAvailableError as e:
                log.warning(
                    "scraper_origin_playwright_unavailable_fallback_httpx",
                    extra={"project_id": ctx.project_id, "error": str(e)},
                )
                use_pw = False

        if use_pw:
            with fetcher_cm as fetch:
                while to_visit and len(results) < max_pages:
                    url = to_visit.pop(0)
                    if url in visited:
                        continue
                    visited.add(url)
                    try:
                        html = fetch.get(url)
                    except Exception as e:  # noqa: BLE001 — Playwright timeout/DNS
                        results.append(self._failed_page(ctx.project_id, url, str(e)))
                        continue
                    self._process_page(
                        html, url, ctx.project_id, source_url, base_host,
                        results, to_visit, visited,
                    )
        else:
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
                    self._process_page(
                        response.text, url, ctx.project_id, source_url, base_host,
                        results, to_visit, visited,
                    )

        # Persistir
        ctx.session.add_all(results)

        # ADR-050 — si el cap se alcanzó y aún quedaban URLs por visitar,
        # generar ResidualTask POST_GO_LIVE para que el operador decida si
        # subir el cap y re-ejecutar scraper_origin.
        cap_reached = len(results) >= max_pages and bool(to_visit)
        if cap_reached:
            ctx.session.add(self._cap_residual(project, max_pages, len(to_visit)))

        ctx.session.flush()

        return AgentResult(
            summary=f"{project.source_url}: {len(results)} páginas scrapeadas",
            outputs={
                "scraped_pages": len(results),
                "successful": sum(1 for p in results if p.status == ScrapeStatus.SUCCESS),
                "failed": sum(1 for p in results if p.status == ScrapeStatus.FAILED),
                "cap_reached": cap_reached,
                "max_pages": max_pages,
                "pending_urls_when_cap_hit": len(to_visit) if cap_reached else 0,
            },
        )

    def _should_use_playwright(self, project: Project) -> bool:
        """ADR-040 — usa Playwright si:
        1. SCRAPE_USE_PLAYWRIGHT=true (override global), o
        2. builder_source ∈ {wix, webflow} (SPAs con JS pesado).
        En cualquier otro caso, httpx (más rápido + menos recursos)."""
        override = os.environ.get("SCRAPE_USE_PLAYWRIGHT", "").lower()
        if override in {"1", "true", "yes"}:
            return True
        if override in {"0", "false", "no"}:
            return False
        builder = (
            project.builder_source.value if project.builder_source else ""
        ).lower()
        return builder in {"wix", "webflow"}

    def _process_page(
        self,
        html: str,
        url: str,
        project_id: int,
        source_url: str,
        base_host: str,
        results: list[ScrapedPage],
        to_visit: list[str],
        visited: set[str],
    ) -> None:
        """Parse HTML + persist + extraer links internos. Compartido entre
        las ramas httpx y Playwright para que el shape de ScrapedPage sea
        idéntico independientemente del fetcher."""
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        lang_tag = soup.find("html")
        page = ScrapedPage(
            project_id=project_id,
            url=url,
            slug=self._url_to_slug(url, source_url),
            title=(title_tag.string.strip() if title_tag and title_tag.string else None),
            lang=(lang_tag.get("lang") if lang_tag and lang_tag.get("lang") else None),
            depth=0,
            html_raw=html,
            html_clean=_sanitize_html(soup),
            status=ScrapeStatus.SUCCESS,
            scraped_at=datetime.now(UTC),
        )
        results.append(page)
        for a in soup.find_all("a", href=True):
            candidate = urljoin(url, a["href"]).split("#")[0]
            if urlparse(candidate).netloc == base_host and candidate not in visited:
                to_visit.append(candidate)

    def _resolve_max_pages(self, project: Project, ctx: AgentContext) -> int:
        """Cascada ADR-050: project.max_pages_scrape > extra > env > 50."""
        if project.max_pages_scrape is not None:
            return int(project.max_pages_scrape)
        if "max_pages" in ctx.extra:
            return int(ctx.extra["max_pages"])
        env_val = os.environ.get("SCRAPE_MAX_PAGES_DEFAULT")
        if env_val:
            try:
                return int(env_val)
            except ValueError:
                log.warning(
                    "scrape_max_pages_default_invalid",
                    extra={"value": env_val},
                )
        return 50

    def _cap_residual(
        self, project: Project, cap: int, pending: int
    ) -> ResidualTask:
        return ResidualTask(
            project_id=project.id,
            title=f"Scraper alcanzó el cap de {cap} páginas",
            description=(
                f"El crawl se detuvo al alcanzar el límite configurado de "
                f"{cap} páginas (project.max_pages_scrape o "
                "SCRAPE_MAX_PAGES_DEFAULT). Quedaban al menos "
                f"{pending} URLs internas pendientes por visitar.\n\n"
                "Acciones:\n"
                "1. Revisar si la web objetivo tiene >cap páginas reales o "
                "es un bucle de parámetros (?p=, ?utm=) — en cuyo caso "
                "ajustar el filtro del scraper.\n"
                "2. Si es contenido real: subir max_pages en "
                "Configuración avanzada del proyecto y re-ejecutar la fase "
                "scrape_origin con Resume + 'Re-ejecutar todo'."
            ),
            category=ResidualCategory.POST_GO_LIVE,
            estimated_minutes=15,
            screenshot_paths=[],
            generated_by="scraper-origin",
            status=ResidualStatus.OPEN,
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
