"""QaRunnerAgent — batería de QA automática post-deploy (v0.16.0).

Verifica que el WordPress destino:
1. Pasa Lighthouse desktop + mobile (performance / a11y / best-practices / SEO).
2. HTML valida en W3C (hasta 50 páginas para respetar rate-limit).
3. No tiene links rotos del propio dominio destino.
4. HTTPS válido + robots.txt + sitemap.xml accesibles.

Persiste una fila nueva en `qa_reports` por ejecución (histórico).
Genera `ResidualTask` para fallos críticos:
- Lighthouse performance desktop o mobile < 50.
- HTML errors > 20.
- Broken links > 5.
- HTTPS inválido.
- robots/sitemap inaccesibles.

Resiliencia:
- Lighthouse no instalado (no Node + lib) → scores=null, residual task
  "instalar `npm install -g lighthouse@^12`". NO bloquea fase.
- W3C API timeout/429 → errors_count=0, warning en summary.
- Link checker no puede acceder al destino → broken_count=0, warning.

Decisión: la fase NO se considera FAILED si los scores son bajos —
solo si NO se pudo ejecutar nada (target inaccesible). Los residuals
quedan en el checklist para que el operador decida si bloquea o no
la entrega.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.qa_reports import QaReport
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ResidualCategory, ResidualStatus, ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import QaRunnerError
from wcm_worker.integrations.html_validator import validate_html
from wcm_worker.integrations.lighthouse import (
    LighthouseNotAvailableError,
    lighthouse_available,
    run_lighthouse,
)
from wcm_worker.integrations.link_checker import LinkReport, check_links

log = logging.getLogger("wcm.worker.qa_runner")

#: Límite de páginas validadas con W3C (rate-limit 1 req/s).
MAX_W3C_PAGES = 50
#: Umbrales para generar residual tasks críticos (ADR-053).
#: Todos overridables via env para ajustar globalmente sin redeploy.
LIGHTHOUSE_PERF_MIN_CRITICAL = int(os.environ.get("LIGHTHOUSE_PERF_MIN_CRITICAL", "50"))
#: ADR-053 — accesibilidad bajo 70 = problemas estructurales graves
#: (sin alt en imágenes, contraste insuficiente, navegación por teclado rota).
#: WCAG 2.1 AA típicamente exige ≥90 para sitios públicos.
LIGHTHOUSE_A11Y_MIN_CRITICAL = int(os.environ.get("LIGHTHOUSE_A11Y_MIN_CRITICAL", "70"))
#: ADR-053 — best-practices bajo 75 = warnings de seguridad (mixed
#: content, vulnerabilidades JS, console errors). Plugins del cliente.
LIGHTHOUSE_BEST_PRACTICES_MIN_CRITICAL = int(
    os.environ.get("LIGHTHOUSE_BEST_PRACTICES_MIN_CRITICAL", "75")
)
#: ADR-053 — SEO bajo 80 = títulos/descriptions faltantes, robots.txt
#: errors, structured data ausente. Compromete posicionamiento.
LIGHTHOUSE_SEO_MIN_CRITICAL = int(os.environ.get("LIGHTHOUSE_SEO_MIN_CRITICAL", "80"))
HTML_ERRORS_MAX_CRITICAL = int(os.environ.get("HTML_ERRORS_MAX_CRITICAL", "20"))
#: ADR-053 — broken_links pasa de threshold absoluto (>5) a fórmula
#: proporcional: max(min_absolute, total * ratio).
BROKEN_LINKS_MIN_ABSOLUTE = int(os.environ.get("BROKEN_LINKS_MIN_ABSOLUTE", "2"))
BROKEN_LINKS_RATIO_THRESHOLD = float(
    os.environ.get("BROKEN_LINKS_RATIO_THRESHOLD", "0.03")
)
#: Compat: el threshold absoluto antiguo queda como fallback para tests
#: que importan el nombre directamente.
BROKEN_LINKS_MAX_CRITICAL = BROKEN_LINKS_MIN_ABSOLUTE


class QaRunnerAgent(BaseAgent):
    name = "qa-runner"
    phase_name = "qa"

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._http = http_client or httpx.Client(timeout=15.0, follow_redirects=True, verify=False)
        self._owns_http = http_client is None

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise QaRunnerError("QaRunnerAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise QaRunnerError(f"Project {ctx.project_id} no encontrado")
        if not project.target_domain:
            raise QaRunnerError(
                f"Project {project.id} sin target_domain — qa-runner requiere "
                "destino para verificar."
            )

        target_host = _strip_protocol(project.target_domain)
        base_url = _build_base_url(project.target_domain)
        warnings: list[str] = []

        try:
            # 1. Lighthouse desktop + mobile (sobre home).
            lh_desktop, lh_mobile, lighthouse_skipped = self._run_lighthouse(base_url, warnings)

            # 2. HTML validator (hasta MAX_W3C_PAGES páginas del scrape).
            html_result = self._validate_html_pages(ctx, project.id, warnings)

            # 3. Link checker.
            link_report = self._check_links(ctx, project.id, target_host, warnings)

            # 4. Checks binarios.
            https_valid = self._check_https(base_url)
            robots_ok = self._check_url_accessible(urljoin(base_url, "/robots.txt"))
            sitemap_ok = self._check_url_accessible(
                urljoin(base_url, "/sitemap.xml")
            ) or self._check_url_accessible(urljoin(base_url, "/sitemap_index.xml"))

            # 5. Persistir reporte.
            report = QaReport(
                project_id=project.id,
                lighthouse_perf_desktop=lh_desktop.performance if lh_desktop else None,
                lighthouse_perf_mobile=lh_mobile.performance if lh_mobile else None,
                lighthouse_a11y_avg=_avg_or_none(
                    lh_desktop.accessibility if lh_desktop else None,
                    lh_mobile.accessibility if lh_mobile else None,
                ),
                lighthouse_best_practices_avg=_avg_or_none(
                    lh_desktop.best_practices if lh_desktop else None,
                    lh_mobile.best_practices if lh_mobile else None,
                ),
                lighthouse_seo_avg=_avg_or_none(
                    lh_desktop.seo if lh_desktop else None,
                    lh_mobile.seo if lh_mobile else None,
                ),
                html_validator_errors_count=html_result["errors"],
                html_validator_warnings_count=html_result["warnings"],
                broken_links_count=link_report.broken_count,
                total_links_checked=link_report.total_checked,
                https_valid=https_valid,
                robots_accessible=robots_ok,
                sitemap_accessible=sitemap_ok,
                report_json={
                    "lighthouse_skipped": lighthouse_skipped,
                    "broken_links": [
                        {
                            "url": b.url,
                            "status_code": b.status_code,
                            "error": b.error,
                            "source_pages": list(b.source_pages),
                        }
                        for b in link_report.broken[:50]
                    ],
                    "html_pages_validated": html_result["pages_validated"],
                },
            )
            ctx.session.add(report)

            # 6. Residual tasks para fallos críticos.
            residuals_created = self._create_residual_tasks(
                ctx,
                project_id=project.id,
                lh_desktop=lh_desktop,
                lh_mobile=lh_mobile,
                html_errors=html_result["errors"],
                broken_links=link_report.broken_count,
                total_links_checked=link_report.total_checked,
                https_valid=https_valid,
                robots_ok=robots_ok,
                sitemap_ok=sitemap_ok,
                lighthouse_skipped=lighthouse_skipped,
            )

            ctx.session.flush()

            perf_summary = (
                f"perf desktop={lh_desktop.performance}/100 mobile={lh_mobile.performance}/100"
                if lh_desktop
                and lh_mobile
                and lh_desktop.performance is not None
                and lh_mobile.performance is not None
                else "Lighthouse SKIPPED"
            )
            return AgentResult(
                summary=(
                    f"Project {project.id} QA · {perf_summary} · "
                    f"HTML errors={html_result['errors']} · "
                    f"broken links={link_report.broken_count}/{link_report.total_checked} · "
                    f"https={https_valid} · {residuals_created} residuals."
                ),
                outputs={
                    "qa_report_id": report.id,
                    "residuals_created": residuals_created,
                },
                warnings=warnings,
                residual_tasks_created=residuals_created,
            )
        finally:
            if self._owns_http:
                self._http.close()

    # ---------- internals ----------

    def _run_lighthouse(self, base_url: str, warnings: list[str]):
        if not lighthouse_available():
            warnings.append("Lighthouse no instalado en server. `npm install -g lighthouse@^12`.")
            return None, None, True
        try:
            desktop = run_lighthouse(base_url, form_factor="desktop")
            mobile = run_lighthouse(base_url, form_factor="mobile")
            return desktop, mobile, False
        except LighthouseNotAvailableError as e:
            warnings.append(f"Lighthouse no disponible: {e}")
            return None, None, True

    def _validate_html_pages(
        self, ctx: AgentContext, project_id: int, warnings: list[str]
    ) -> dict[str, int]:
        stmt = (
            select(ScrapedPage)
            .where(
                ScrapedPage.project_id == project_id,
                ScrapedPage.status == ScrapeStatus.SUCCESS,
                ScrapedPage.html_clean.isnot(None),
            )
            .order_by(ScrapedPage.depth.asc())
            .limit(MAX_W3C_PAGES)
        )
        pages = list(ctx.session.execute(stmt).scalars().all())
        errors_total = 0
        warnings_total = 0
        for page in pages:
            try:
                result = validate_html(page.html_clean or "", url=page.url)
                errors_total += len(result.errors)
                warnings_total += len(result.warnings)
            except Exception as e:  # noqa: BLE001 — defensa extra; el helper ya degrada
                log.warning(
                    "html_validator_failed_for_page",
                    extra={"url": page.url, "error": str(e)},
                )
                warnings.append(f"HTML validator falló en {page.url}: {type(e).__name__}")
        return {
            "errors": errors_total,
            "warnings": warnings_total,
            "pages_validated": len(pages),
        }

    def _check_links(
        self,
        ctx: AgentContext,
        project_id: int,
        target_host: str,
        warnings: list[str],
    ) -> LinkReport:
        stmt = (
            select(ScrapedPage)
            .where(
                ScrapedPage.project_id == project_id,
                ScrapedPage.status == ScrapeStatus.SUCCESS,
            )
            .order_by(ScrapedPage.depth.asc())
        )
        pages = list(ctx.session.execute(stmt).scalars().all())
        if not pages:
            warnings.append("Sin scraped_pages — link checker SKIPPED.")
            return LinkReport()

        target_urls = []
        for page in pages:
            parsed = urlparse(page.url)
            path = parsed.path or "/"
            target_urls.append(f"https://{target_host}{path}")
        try:
            return check_links(target_urls, target_host=target_host, http_client=self._http)
        except Exception as e:  # noqa: BLE001
            log.warning("link_checker_failed", extra={"error": str(e)})
            warnings.append(f"Link checker falló: {type(e).__name__}")
            return LinkReport()

    def _check_https(self, base_url: str) -> bool | None:
        """Verifica que la URL responde con HTTPS válido. None si timeout."""
        if not base_url.startswith("https://"):
            return False
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True, verify=True) as c:
                resp = c.head(base_url)
                return resp.status_code < 500
        except httpx.HTTPError:
            return False
        except Exception:  # noqa: BLE001 — SSLError u otros
            return None

    def _check_url_accessible(self, url: str) -> bool:
        try:
            resp = self._http.head(url)
            if resp.status_code == 405:
                resp = self._http.get(url, headers={"Range": "bytes=0-1023"})
            return resp.status_code < 400
        except (httpx.HTTPError, httpx.TimeoutException):
            return False

    def _create_residual_tasks(
        self,
        ctx: AgentContext,
        *,
        project_id: int,
        lh_desktop,
        lh_mobile,
        html_errors: int,
        broken_links: int,
        total_links_checked: int = 0,
        https_valid: bool | None,
        robots_ok: bool,
        sitemap_ok: bool,
        lighthouse_skipped: bool,
    ) -> int:
        """Crea ResidualTask por cada fallo crítico. Devuelve cuántos creó."""
        created = 0

        def _add(title: str, description: str, category: ResidualCategory) -> None:
            nonlocal created
            ctx.session.add(
                ResidualTask(
                    project_id=project_id,
                    title=title,
                    description=description,
                    category=category,
                    status=ResidualStatus.OPEN,
                    estimated_minutes=15,
                    generated_by="qa-runner",
                )
            )
            created += 1

        if lighthouse_skipped:
            _add(
                "Instalar Lighthouse en el servidor del worker",
                "Para QA automático ejecuta `npm install -g lighthouse@^12` "
                "en el server. Sin esto los scores de performance/a11y/best-"
                "practices/SEO no se miden.",
                ResidualCategory.CLIENT_CONFIG,
            )

        for label, lh in (("desktop", lh_desktop), ("mobile", lh_mobile)):
            if lh and lh.performance is not None and lh.performance < LIGHTHOUSE_PERF_MIN_CRITICAL:
                _add(
                    f"Lighthouse performance {label} bajo ({lh.performance}/100)",
                    f"Lighthouse {label} marca performance < {LIGHTHOUSE_PERF_MIN_CRITICAL}. "
                    "Revisa imágenes pesadas, CSS/JS unminified, fonts blocking. "
                    "Usa PageSpeed Insights para diagnóstico detallado.",
                    ResidualCategory.POST_GO_LIVE,
                )

        # ADR-053 — accesibilidad, best-practices, SEO. Promediados
        # desktop+mobile en lh_*_avg que el agente ya calculó.
        # Para mantener simple, evaluamos a11y de lh_desktop si existe
        # (típicamente es el más representativo del sitio).
        lh_for_extras = lh_desktop or lh_mobile
        if lh_for_extras:
            if (
                lh_for_extras.accessibility is not None
                and lh_for_extras.accessibility < LIGHTHOUSE_A11Y_MIN_CRITICAL
            ):
                _add(
                    f"Mejorar accesibilidad (score {lh_for_extras.accessibility}/100)",
                    f"Lighthouse marca accesibilidad < {LIGHTHOUSE_A11Y_MIN_CRITICAL}. "
                    "Causas comunes: imágenes sin `alt`, contraste insuficiente, "
                    "navegación por teclado rota, ARIA mal usado. WCAG 2.1 AA "
                    "exige ≥90 para sitios públicos en UE (LOPDGDD-LGGDP). "
                    "Detalles: https://web.dev/learn/accessibility/",
                    ResidualCategory.POST_GO_LIVE,
                )
            if (
                lh_for_extras.best_practices is not None
                and lh_for_extras.best_practices < LIGHTHOUSE_BEST_PRACTICES_MIN_CRITICAL
            ):
                _add(
                    f"Mejorar buenas prácticas (score {lh_for_extras.best_practices}/100)",
                    f"Lighthouse marca best-practices < {LIGHTHOUSE_BEST_PRACTICES_MIN_CRITICAL}. "
                    "Causas comunes: mixed content HTTPS/HTTP, vulnerabilidades JS "
                    "conocidas (jQuery viejo, etc.), console errors. "
                    "Detalles: https://web.dev/best-practices-score/",
                    ResidualCategory.POST_GO_LIVE,
                )
            if (
                lh_for_extras.seo is not None
                and lh_for_extras.seo < LIGHTHOUSE_SEO_MIN_CRITICAL
            ):
                _add(
                    f"Mejorar SEO técnico (score {lh_for_extras.seo}/100)",
                    f"Lighthouse marca SEO < {LIGHTHOUSE_SEO_MIN_CRITICAL}. "
                    "Causas comunes: títulos/descriptions duplicados o faltantes, "
                    "robots.txt mal, structured data ausente, links sin texto. "
                    "Detalles: https://web.dev/lighthouse-seo/",
                    ResidualCategory.POST_GO_LIVE,
                )

        if html_errors > HTML_ERRORS_MAX_CRITICAL:
            _add(
                f"HTML inválido ({html_errors} errores W3C)",
                f"El validador W3C reporta {html_errors} errores HTML "
                f"(umbral crítico: {HTML_ERRORS_MAX_CRITICAL}). Revisa los "
                "detalles en el reporte qa_reports.report_json. Errores "
                "comunes: tags no cerrados, attrs deprecated, ARIA incorrecto.",
                ResidualCategory.POST_GO_LIVE,
            )

        # ADR-053 — broken_links proporcional. Más estricto en webs
        # pequeñas (2 broken en 5 páginas), más laxo en grandes (15 en 500).
        broken_threshold = max(
            BROKEN_LINKS_MIN_ABSOLUTE,
            int(total_links_checked * BROKEN_LINKS_RATIO_THRESHOLD),
        )
        if broken_links > broken_threshold:
            ratio_pct = (
                int(broken_links * 100 / total_links_checked)
                if total_links_checked > 0
                else 0
            )
            _add(
                f"Links rotos en el destino ({broken_links}/{total_links_checked} URLs 4xx/5xx, {ratio_pct}%)",
                f"Detectados {broken_links} links del propio dominio que "
                f"responden 4xx/5xx, sobre {total_links_checked} comprobados "
                f"(threshold proporcional: > max({BROKEN_LINKS_MIN_ABSOLUTE}, "
                f"{int(BROKEN_LINKS_RATIO_THRESHOLD * 100)}% del total) = "
                f"{broken_threshold}). Lista detallada en qa_reports.report_json. "
                "Causas típicas: páginas migradas con paths distintos, redirects "
                "rotos, recursos eliminados.",
                ResidualCategory.BLOCKING_GO_LIVE,
            )

        if https_valid is False:
            _add(
                "HTTPS inválido o no disponible en el destino",
                "El dominio destino NO responde con HTTPS válido. "
                "Configura SSL (Let's Encrypt vía cPanel o certbot) antes "
                "de salir a producción.",
                ResidualCategory.BLOCKING_GO_LIVE,
            )

        if not robots_ok:
            _add(
                "robots.txt no accesible en el destino",
                "`/robots.txt` devuelve error o 404. Si la web debe ser "
                "indexable, configura robots.txt permitiendo crawlers; "
                "si no, al menos un archivo vacío para evitar 404 SEO.",
                ResidualCategory.CLIENT_CONFIG,
            )

        if not sitemap_ok:
            _add(
                "sitemap.xml no accesible en el destino",
                "Ni `/sitemap.xml` ni `/sitemap_index.xml` responden. "
                "Instala Yoast SEO o Rank Math (auto-generan sitemap) o "
                "genera uno manual. Importante para indexación Google.",
                ResidualCategory.CLIENT_CONFIG,
            )

        return created


def _strip_protocol(domain: str) -> str:
    """`https://foo.es` → `foo.es`."""
    if domain.startswith("http://"):
        return domain[len("http://") :].rstrip("/")
    if domain.startswith("https://"):
        return domain[len("https://") :].rstrip("/")
    return domain.rstrip("/")


def _build_base_url(domain: str) -> str:
    if domain.startswith(("http://", "https://")):
        return domain.rstrip("/") + "/"
    return f"https://{domain.rstrip('/')}/"


def _avg_or_none(*values: int | None) -> int | None:
    """Promedio entero de scores no-None. None si todos None."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    return round(sum(non_null) / len(non_null))
