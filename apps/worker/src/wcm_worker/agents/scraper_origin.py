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
        # Fix 2026-05-20 (A.2): canonicalizar el source_url y todas las URLs
        # que el BFS encuentra. Sin esto, `https://foo.com` y
        # `https://www.foo.com` se procesan como páginas distintas y
        # acaban produciendo dos `scraped_pages` para la misma página,
        # provocando UniqueViolation en fase `transpile_bricks` por slug
        # duplicado. El canonical fija un solo formato (host sin `www.`,
        # path sin trailing slash, sin fragmento).
        source_url = self._canonical_url(project.source_url.rstrip("/"))
        base_host = urlparse(source_url).netloc

        # v0.18.0 — Si el cliente nos dio credenciales del back, sembrar el
        # BFS con la lista canónica de URLs de la API oficial. Esto descubre
        # páginas que el menú público NO enlaza directamente (privacidad,
        # legal, landing pages sueltas). Si la API falla por cualquier motivo,
        # caemos al BFS tradicional desde source_url.
        seed_urls = [self._canonical_url(u) for u in self._seed_from_api(project)]

        # BFS simple. Por seguridad: nunca seguimos links a otros dominios.
        # Las URLs en to_visit y visited son SIEMPRE canónicas.
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
            # AI.1 — R2 lazy: solo se inicializa si hay screenshots que subir.
            r2_client = None
            with fetcher_cm as fetch:
                while to_visit and len(results) < max_pages:
                    url = to_visit.pop(0)
                    if url in visited:
                        continue
                    visited.add(url)
                    try:
                        fetched = fetch.get(url)
                    except Exception as e:  # noqa: BLE001 — Playwright timeout/DNS
                        results.append(self._failed_page(ctx.project_id, url, str(e)))
                        continue
                    # AI.1 — recortar full-page + subir secciones a R2.
                    section_urls: list[dict[str, Any]] = []
                    if (
                        fetched.full_page_png
                        and fetched.section_bboxes
                    ):
                        if r2_client is None:
                            r2_client = self._init_r2_client()
                        section_urls = self._upload_section_screenshots(
                            r2_client,
                            ctx.project_id,
                            len(results),  # idx temporal — se reescribe en _process_page
                            fetched.full_page_png,
                            fetched.section_bboxes,
                        )
                    self._process_page(
                        fetched.html, url, ctx.project_id, source_url, base_host,
                        results, to_visit, visited,
                        css_extracted=fetched.stylesheets,
                        computed_styles=fetched.computed_styles,
                        section_screenshots=section_urls,
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
                        css_extracted="",
                        computed_styles={},
                        section_screenshots=[],
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
        *,
        css_extracted: str = "",
        computed_styles: dict[str, dict[str, str]] | None = None,
        section_screenshots: list[dict[str, Any]] | None = None,
    ) -> None:
        """Parse HTML + persist + extraer links internos. Compartido entre
        las ramas httpx y Playwright para que el shape de ScrapedPage sea
        idéntico independientemente del fetcher.

        C.2: si llega `css_extracted` (rama Playwright con
        `capture_styles=True`), se persiste en la columna homónima de
        `scraped_pages`. `computed_styles` se guarda en `dom_tree_json`
        para que `theme_styles_agent` lo sintetice.
        """
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
            css_extracted=css_extracted or None,
            dom_tree_json=computed_styles or None,
            section_screenshots_json=section_screenshots or None,
            status=ScrapeStatus.SUCCESS,
            scraped_at=datetime.now(UTC),
        )
        results.append(page)
        for a in soup.find_all("a", href=True):
            candidate = urljoin(url, a["href"]).split("#")[0]
            if not self._same_site(candidate, base_host):
                continue
            canonical = self._canonical_url(candidate)
            if canonical not in visited:
                to_visit.append(canonical)

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
    def _init_r2_client():
        """AI.1 — Inicializa R2Client desde env. None si R2 no configurado.

        Importado dentro de la función para evitar dep circular en tests.
        """
        from wcm_worker.integrations.r2 import R2Client

        return R2Client.from_env()

    def _upload_section_screenshots(
        self,
        r2_client: Any,
        project_id: int,
        page_idx: int,
        full_page_png: bytes,
        section_bboxes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """AI.1 — Recorta el full-page PNG por cada bbox de sección y sube
        cada recorte a R2. Devuelve `[{idx, selector, url}]`.

        Si R2 no está configurado (`r2_client is None`) o Pillow no
        instalado, devuelve lista vacía (graceful degradation — ai_assist
        seguirá funcionando con HTML solo, sin vision).
        """
        if r2_client is None or not full_page_png or not section_bboxes:
            return []
        try:
            import io

            from PIL import Image
        except ImportError:
            log.warning("scraper_origin_pillow_missing")
            return []

        try:
            img = Image.open(io.BytesIO(full_page_png))
        except Exception as e:  # noqa: BLE001
            log.warning(
                "scraper_origin_full_page_image_open_failed",
                extra={"project_id": project_id, "error": str(e)[:200]},
            )
            return []

        results: list[dict[str, Any]] = []
        for entry in section_bboxes:
            try:
                bbox = entry.get("bbox") or {}
                x = int(bbox.get("x", 0))
                y = int(bbox.get("y", 0))
                w = int(bbox.get("w", 0))
                h = int(bbox.get("h", 0))
                if w <= 0 or h <= 0:
                    continue
                # Clamp al tamaño del PNG (los bboxes pueden exceder por
                # ~1px en algunos casos por floats).
                x2 = min(x + w, img.width)
                y2 = min(y + h, img.height)
                if x >= img.width or y >= img.height or x2 <= x or y2 <= y:
                    continue
                crop = img.crop((x, y, x2, y2))
                buf = io.BytesIO()
                crop.save(buf, format="PNG", optimize=True)
                idx = int(entry.get("idx", len(results)))
                key = (
                    f"wcm/projects/{project_id}/sections/"
                    f"{page_idx}/{idx}.png"
                )
                url = r2_client.put_bytes(
                    key,
                    buf.getvalue(),
                    content_type="image/png",
                    metadata={
                        "project_id": str(project_id),
                        "page_idx": str(page_idx),
                        "section_idx": str(idx),
                    },
                )
                results.append({
                    "idx": idx,
                    "selector": entry.get("selector"),
                    "url": url,
                })
            except Exception as e:  # noqa: BLE001 — un recorte fallido no rompe la página
                log.warning(
                    "scraper_origin_section_crop_failed",
                    extra={
                        "project_id": project_id,
                        "section_idx": entry.get("idx"),
                        "error": str(e)[:200],
                    },
                )
                continue
        return results

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
    def _url_to_slug(url: str, base_url: str = "") -> str:
        """Slug = path del URL sin barras. `base_url` se acepta por
        compatibilidad pero ya no se usa: si el sitio responde con `www.`
        y `source_url` no lo lleva (o viceversa), el `removeprefix`
        anterior fallaba y devolvía la URL completa como slug. Ahora
        usamos `urlparse(url).path` que es agnóstico al host.
        """
        path = urlparse(url).path.strip("/")
        return path or "home"

    @staticmethod
    def _norm_host(host: str) -> str:
        """Normaliza host para comparación: minúsculas + sin prefix `www.`."""
        return host.lower().removeprefix("www.")

    @staticmethod
    def _canonical_url(url: str) -> str:
        """URL canónica para deduplicación en BFS (fix 2026-05-20 A.2).

        Reglas:
        - Host: minúsculas, sin prefix `www.`
        - Path: sin trailing slash (excepto raíz `/`)
        - Sin fragmento (`#...`)
        - Query preservada (puede afectar contenido en sitios dinámicos)

        Ejemplo:
            https://Foo.com/about/ → https://foo.com/about
            https://www.foo.com/   → https://foo.com/
            https://foo.com#hash   → https://foo.com/
        """
        try:
            parts = urlparse(url)
        except ValueError:
            return url
        if not parts.netloc:
            return url
        host = parts.netloc.lower().removeprefix("www.")
        path = parts.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        query = f"?{parts.query}" if parts.query else ""
        scheme = parts.scheme or "https"
        return f"{scheme}://{host}{path}{query}"

    @staticmethod
    def _same_site(url: str, ref_host: str) -> bool:
        """True si `url` pertenece al mismo sitio que `ref_host`.

        Tolera el prefix `www.` en cualquiera de los dos lados pero NO
        otros subdominios (`blog.foo.com` ≠ `foo.com`) ni distinto host.
        Las URLs sin host (mailto, tel, javascript) devuelven False.
        """
        try:
            netloc = urlparse(url).netloc
        except ValueError:
            return False
        if not netloc:
            return False
        return ScraperOriginAgent._norm_host(netloc) == ScraperOriginAgent._norm_host(
            ref_host
        )


def _sanitize_html(soup: BeautifulSoup) -> str:
    """Sanitización ligera: eliminar scripts, tracking, comments."""
    for tag in soup.find_all(["script", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"data-wix-bi": True}):
        tag.decompose()
    return str(soup)
