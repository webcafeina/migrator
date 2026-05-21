"""VisualDiffAgent — compara visualmente cada página origen vs destino (v0.16.0).

Flujo:
1. Carga `ScrapedPage` del proyecto (status=SUCCESS).
2. Calcula URL destino para cada página: `https://{target_domain}{path}`.
3. Abre 1 browser Playwright + 1 context (resource sharing).
4. Por cada página: captura origen + captura destino → pixelmatch → score.
5. Sube las 3 PNG (source/target/overlay) a R2 si configurado, o
   `file://` local fallback.
6. UPSERT en `visual_diffs` (project_id, page_path).
7. Recalcula `projects.visual_diff_avg_score` con el promedio.

Resiliencia:
- Playwright no instalado → SKIPPED + ResidualTask.
- Target domain inaccesible (timeout en goto) → fila con score=0, URLs
  parciales, warning en `AgentResult.warnings`. NO rompe la fase entera.
- R2 no configurado → paths `file://...` locales (utilidad limitada;
  el operador ve dummy en UI hasta configurar R2 + re-ejecutar).
- Project sin scraped_pages → fase completa con summary "0 páginas".

Decisión: re-ejecutar el agent SOBRESCRIBE las filas existentes
(UPSERT). El histórico no se conserva — el operador siempre quiere
ver el último diff.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_db.models.visual_diffs import VisualDiff
from wcm_types.enums import (
    ResidualCategory,
    ResidualStatus,
    ScrapeStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import VisualDiffError
from wcm_worker.integrations.playwright_screenshot import (
    PlaywrightNotAvailableError,
    screenshot_session,
)
from wcm_worker.integrations.r2 import R2Client
from wcm_worker.integrations.visual_diff_compare import compare

log = logging.getLogger("wcm.worker.visual_diff")

#: Viewport por defecto. 1280×800 cubre la mayoría de breakpoints
#: desktop sin entrar en modo grande (1920+ tiene scroll horizontal
#: en muchas plantillas).
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800

#: Threshold pixelmatch. 0.15 es más laxo que el default 0.1 — tolera
#: pequeños shifts de typography (anti-aliasing, font rendering OS).
DEFAULT_DIFF_THRESHOLD = 0.15

#: Timeout corto para captura del target (URL destino). Si las páginas
#: están en draft (404 público), se acaba en 8s en lugar de 30s del
#: default. Source sigue con 30s — el origen tarda más en hidratarse
#: (Wix con trackers). Override por env VISUAL_DIFF_TARGET_TIMEOUT_MS.
DEFAULT_TARGET_TIMEOUT_MS = 8_000

#: Pre-check: timeout en segundos para la petición HTTP de validación
#: del destino antes de abrir Playwright. 5s suficiente para confirmar
#: si el target devuelve 200/3xx o 404.
DEFAULT_PRECHECK_TIMEOUT_S = 5.0

#: Cap de fallos consecutivos. Si el bucle encadena N timeouts/errores,
#: abortamos asumiendo que el destino no es accesible y evitamos
#: consumir minutos en timeouts encadenados. Override por env
#: VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES.
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class PrecheckResult:
    """Resultado del pre-check del destino antes del bucle de capturas.

    Si `skip_reason` es non-None, visual_diff aborta inmediatamente con
    SKIPPED + residual task; no se abre Playwright ni se itera páginas.
    """

    skip_reason: str | None = None
    detail: str = ""
    status_code: int | None = None


class VisualDiffAgent(BaseAgent):
    name = "visual-diff"
    phase_name = "visual_diff"

    def __init__(self, *, r2: R2Client | None = None) -> None:
        self._injected_r2 = r2

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise VisualDiffError("VisualDiffAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise VisualDiffError(f"Project {ctx.project_id} no encontrado")
        if not project.target_domain:
            raise VisualDiffError(
                f"Project {project.id} sin target_domain — visual-diff requiere "
                "destino para comparar. Configura target_domain antes de ejecutar."
            )

        pages = self._load_pages(ctx, project.id)
        if not pages:
            return AgentResult(
                summary=f"Project {project.id}: sin páginas scrapeadas para comparar.",
                outputs={"pages_compared": 0, "avg_score": None},
                warnings=["scraped_pages vacío — ¿se ejecutó scraper-origin?"],
            )

        r2 = self._injected_r2 or R2Client.from_env()
        residual_threshold = self._resolve_residual_threshold(project)
        max_consecutive_failures = self._resolve_max_consecutive_failures()
        target_timeout_ms = self._resolve_target_timeout_ms()
        warnings: list[str] = []
        scores: list[float] = []
        below_threshold: list[tuple[str, float]] = []
        compared = 0
        failed_pages = 0

        # D.1 — Pre-check antes de abrir Playwright. Si el destino devuelve
        # 404 para la primera página esperada (caso típico: páginas en
        # draft tras deploy_wp por ADR-039), abortamos limpio con
        # SKIPPED + residual. Antes consumíamos 25-45 min en timeouts
        # encadenados de Playwright.
        precheck = self._precheck_target(project.target_domain, pages[0])
        if precheck.skip_reason:
            ctx.session.add(self._draft_pages_residual(project, precheck.detail))
            ctx.session.flush()
            log.info(
                "visual_diff_precheck_skip",
                extra={
                    "project_id": project.id,
                    "reason": precheck.skip_reason,
                    "status_code": precheck.status_code,
                },
            )
            return AgentResult(
                summary=(
                    f"Project {project.id}: visual-diff SKIPPED — "
                    f"{precheck.skip_reason}"
                ),
                outputs={
                    "skipped": True,
                    "reason": precheck.skip_reason,
                    "pages_compared": 0,
                    "precheck_status_code": precheck.status_code,
                },
                warnings=[precheck.detail],
            )

        try:
            session_cm = screenshot_session(
                viewport_width=DEFAULT_VIEWPORT_WIDTH,
                viewport_height=DEFAULT_VIEWPORT_HEIGHT,
            )
        except PlaywrightNotAvailableError as e:
            # Caso clásico: server sin chromium. Marcar warning y salir
            # OK pero con summary explicativo (el orchestrator decide
            # si esto bloquea según required flag).
            return AgentResult(
                summary=(
                    f"Project {project.id}: visual-diff SKIPPED — Playwright "
                    "no disponible. Instalar en server: "
                    "`playwright install chromium` + `playwright install-deps`."
                ),
                outputs={"skipped": True, "reason": str(e)},
                warnings=[f"Playwright no instalado: {e}"],
            )

        consecutive_failures = 0
        aborted_early = False
        try:
            with session_cm as session_pw:
                for page in pages:
                    page_path = _extract_path(page.url)
                    target_url = _build_target_url(project.target_domain, page_path)
                    try:
                        source_png = session_pw.capture(page.url)
                        # D.2 — timeout corto para target. Si la página no
                        # existe (draft, 404), falla en target_timeout_ms
                        # en vez del default 30s.
                        target_png = session_pw.capture(
                            target_url, timeout_ms=target_timeout_ms
                        )
                    except Exception as e:  # noqa: BLE001 — Playwright timeout, DNS, etc.
                        failed_pages += 1
                        consecutive_failures += 1
                        log.warning(
                            "visual_diff_page_failed",
                            extra={
                                "project_id": project.id,
                                "page_path": page_path,
                                "error": str(e),
                                "consecutive_failures": consecutive_failures,
                            },
                        )
                        warnings.append(
                            f"Fallo capturando {page_path}: {type(e).__name__}: {str(e)[:120]}"
                        )
                        # D.3 — cap fallos consecutivos. Si llegamos al
                        # límite, asumimos que el destino no está
                        # accesible y abortamos para no quemar minutos.
                        if consecutive_failures >= max_consecutive_failures:
                            aborted_early = True
                            warnings.append(
                                f"Bucle abortado tras {max_consecutive_failures} "
                                f"fallos consecutivos."
                            )
                            ctx.session.add(
                                self._consecutive_failures_residual(
                                    project,
                                    max_consecutive_failures,
                                    len(pages) - compared - failed_pages,
                                )
                            )
                            break
                        continue
                    consecutive_failures = 0

                    try:
                        result = compare(source_png, target_png, threshold=DEFAULT_DIFF_THRESHOLD)
                    except Exception as e:  # noqa: BLE001 — pixelmatch corner cases
                        failed_pages += 1
                        log.warning(
                            "visual_diff_compare_failed",
                            extra={
                                "project_id": project.id,
                                "page_path": page_path,
                                "error": str(e),
                            },
                        )
                        warnings.append(f"Comparación falló en {page_path}: {type(e).__name__}")
                        continue

                    src_url, tgt_url, ovr_url = self._upload_three(
                        r2,
                        project_id=project.id,
                        page_path=page_path,
                        source_png=source_png,
                        target_png=target_png,
                        overlay_png=result.overlay_png,
                    )

                    self._upsert_visual_diff(
                        ctx,
                        project_id=project.id,
                        page_path=page_path,
                        source_url=src_url,
                        target_url=tgt_url,
                        overlay_url=ovr_url,
                        score=result.score,
                    )
                    scores.append(result.score)
                    compared += 1
                    if result.score < residual_threshold:
                        below_threshold.append((page_path, result.score))
        finally:
            # session_pw cleanup ya por context manager.
            pass

        avg_score = sum(scores) / len(scores) if scores else None
        if avg_score is not None:
            project.visual_diff_avg_score = avg_score

        # ADR-044 — una ResidualTask VISUAL_CONTENT por página bajo umbral.
        for page_path, score in below_threshold:
            ctx.session.add(
                self._below_threshold_residual(
                    project, page_path, score, residual_threshold
                )
            )

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: {compared}/{len(pages)} páginas comparadas. "
                f"Score medio: {avg_score:.2f}."
                if avg_score is not None
                else f"Project {project.id}: 0 páginas comparadas con éxito ({failed_pages} fallos)."
            ),
            outputs={
                "pages_compared": compared,
                "pages_failed": failed_pages,
                "avg_score": avg_score,
                "residual_threshold": residual_threshold,
                "pages_below_threshold": len(below_threshold),
                "aborted_early": aborted_early,
            },
            warnings=warnings,
        )

    # ---------- ADR-044 helpers ----------

    def _resolve_residual_threshold(self, project: Project) -> float:
        """Cascada ADR-044: project.visual_diff_threshold > env > 0.70."""
        if project.visual_diff_threshold is not None:
            return float(project.visual_diff_threshold)
        env_val = os.environ.get("VISUAL_DIFF_RESIDUAL_THRESHOLD")
        if env_val:
            try:
                return float(env_val)
            except ValueError:
                log.warning(
                    "visual_diff_residual_threshold_invalid",
                    extra={"value": env_val},
                )
        return 0.70

    def _resolve_max_consecutive_failures(self) -> int:
        """Cap configurable por env VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES."""
        env_val = os.environ.get("VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES")
        if env_val:
            try:
                v = int(env_val)
                if v >= 1:
                    return v
            except ValueError:
                log.warning(
                    "visual_diff_max_consecutive_failures_invalid",
                    extra={"value": env_val},
                )
        return DEFAULT_MAX_CONSECUTIVE_FAILURES

    def _resolve_target_timeout_ms(self) -> int:
        """Timeout per-capture del target. Override por env."""
        env_val = os.environ.get("VISUAL_DIFF_TARGET_TIMEOUT_MS")
        if env_val:
            try:
                v = int(env_val)
                if v >= 1000:
                    return v
            except ValueError:
                log.warning(
                    "visual_diff_target_timeout_invalid",
                    extra={"value": env_val},
                )
        return DEFAULT_TARGET_TIMEOUT_MS

    def _precheck_target(
        self, target_domain: str, first_page: ScrapedPage
    ) -> PrecheckResult:
        """D.1 — Verifica que el destino sirva la primera página esperada.

        Caso típico que esto evita: tras `deploy_wp` las páginas WP quedan
        en `status=draft` (ADR-039) y devuelven 404 público. Sin este
        pre-check, visual_diff itera las 50 páginas cada una con 30s de
        timeout Playwright → 25-45 min consumidos en timeouts encadenados.

        Política:
        - 200/3xx (con follow_redirects)  → OK, continuar.
        - 404  → skip con razón "páginas en draft".
        - Otros >=400 → skip con razón "destino con error".
        - Network error  → skip con razón "destino inaccesible".
        """
        page_path = _extract_path(first_page.url)
        target_url = _build_target_url(target_domain, page_path)
        # D.4 — respetar WP_VERIFY_SSL (misma env var que el WP REST
        # client). En dev con cert auto-firmado, sin esto el pre-check
        # cae por SSLError y reporta falso "Destino inaccesible" cuando
        # realmente el destino está vivo, solo no tiene cert válido.
        verify_ssl = os.environ.get("WP_VERIFY_SSL", "true").lower() not in (
            "0", "false", "no"
        )
        try:
            resp = httpx.get(
                target_url,
                timeout=DEFAULT_PRECHECK_TIMEOUT_S,
                follow_redirects=True,
                verify=verify_ssl,
                headers={"User-Agent": "WebcafeinaMigrator/0.1 (visual-diff precheck)"},
            )
        except httpx.RequestError as e:
            return PrecheckResult(
                skip_reason="Destino inaccesible",
                detail=(
                    f"GET {target_url} falló: {type(e).__name__}: {str(e)[:200]}. "
                    "Verifica que el dominio target esté apuntado al WP destino "
                    "y que el server responda."
                ),
            )
        if resp.status_code == 404:
            return PrecheckResult(
                skip_reason="Páginas WP destino en draft (404 público)",
                detail=(
                    f"GET {target_url} → HTTP 404. Las páginas creadas por "
                    "deploy_wp quedan en status=draft por diseño (ADR-039: la "
                    "publicación es decisión humana). Para validar visualmente: "
                    "pulsa 'Publicar todo' en el dashboard del proyecto y "
                    "luego ejecuta Resume sobre visual_diff."
                ),
                status_code=404,
            )
        if resp.status_code >= 400:
            return PrecheckResult(
                skip_reason=f"Destino devuelve HTTP {resp.status_code}",
                detail=f"GET {target_url} → HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        return PrecheckResult(status_code=resp.status_code)

    def _draft_pages_residual(self, project: Project, detail: str) -> ResidualTask:
        """ResidualTask cuando el pre-check detecta drafts (404)."""
        return ResidualTask(
            project_id=project.id,
            title="Publicar páginas WP destino + re-ejecutar visual_diff",
            description=(
                "Visual_diff se saltó porque las páginas WP creadas por "
                "deploy_wp están en `draft` (ADR-039: la publicación es "
                "decisión humana, no automática).\n\n"
                f"Diagnóstico: {detail}\n\n"
                "Pasos:\n"
                "1. Abre cada página en wp-admin "
                "(`/wp-admin/edit.php?post_type=page`) y revisa el render "
                "del Bricks editor.\n"
                "2. Cuando estés conforme con el contenido, pulsa "
                "**'Publicar todo'** en el dashboard del proyecto.\n"
                "3. Reanuda la fase visual_diff: "
                "`POST /projects/{pid}/resume` con `force_phase=visual_diff`."
            ).format(pid=project.id),
            category=ResidualCategory.POST_GO_LIVE,
            estimated_minutes=15,
            screenshot_paths=[],
            generated_by="visual-diff",
            status=ResidualStatus.OPEN,
        )

    def _consecutive_failures_residual(
        self, project: Project, cap: int, remaining: int
    ) -> ResidualTask:
        """ResidualTask cuando el bucle aborta por cap de fallos consecutivos."""
        return ResidualTask(
            project_id=project.id,
            title=f"visual_diff abortado tras {cap} fallos consecutivos",
            description=(
                f"El bucle se cortó tras {cap} fallos consecutivos al "
                "capturar el destino. Quedaron aproximadamente "
                f"{remaining} páginas sin comparar.\n\n"
                "Causa probable: las páginas WP destino están caídas, "
                "en draft, o el target_domain apunta a un sitio incorrecto.\n\n"
                "Acciones:\n"
                "1. Verifica `https://{target}` en navegador.\n"
                "2. Si todas las páginas están en draft, publica primero "
                "y reanuda visual_diff.\n"
                "3. Si quieres elevar el cap, configura "
                "`VISUAL_DIFF_MAX_CONSECUTIVE_FAILURES=N` en `.env` y "
                "reanuda."
            ).format(target=project.target_domain or "<target_domain>"),
            category=ResidualCategory.POST_GO_LIVE,
            estimated_minutes=15,
            screenshot_paths=[],
            generated_by="visual-diff",
            status=ResidualStatus.OPEN,
        )

    def _below_threshold_residual(
        self,
        project: Project,
        page_path: str,
        score: float,
        threshold: float,
    ) -> ResidualTask:
        return ResidualTask(
            project_id=project.id,
            title=f"Visual diff bajo umbral en {page_path} ({score:.2f} < {threshold:.2f})",
            description=(
                f"La página `{page_path}` tiene similitud visual de "
                f"{score:.2f} respecto al origen, bajo el umbral "
                f"configurado de {threshold:.2f}. Revisar el overlay en "
                "/projects/{pid}/diff y decidir si:\n\n"
                "1. La divergencia es cosmética aceptable (cerrar como skipped).\n"
                "2. Falta contenido/imagen → editar la página en Bricks.\n"
                "3. El threshold del proyecto está mal calibrado → ajustar en "
                "Configuración avanzada del proyecto."
            ).format(pid=project.id),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=20,
            screenshot_paths=[],
            generated_by="visual-diff",
            status=ResidualStatus.OPEN,
        )

    # ---------- helpers ----------

    def _load_pages(self, ctx: AgentContext, project_id: int) -> list[ScrapedPage]:
        stmt = (
            select(ScrapedPage)
            .where(
                ScrapedPage.project_id == project_id,
                ScrapedPage.status == ScrapeStatus.SUCCESS,
            )
            .order_by(ScrapedPage.depth.asc(), ScrapedPage.id.asc())
        )
        return list(ctx.session.execute(stmt).scalars().all())

    def _upload_three(
        self,
        r2: R2Client | None,
        *,
        project_id: int,
        page_path: str,
        source_png: bytes,
        target_png: bytes,
        overlay_png: bytes,
    ) -> tuple[str | None, str | None, str | None]:
        """Sube los 3 PNG a R2. Si r2 es None, devuelve `file://`
        paths a /tmp para diagnóstico local (el dashboard NO renderiza
        file:// — solo útil dev).
        """
        slug = _slugify(page_path)
        # W (2026-05-21) — prefijo unificado `wcm/projects/{id}/` (antes
        # era `projects/{id}/` aquí pero `wcm/projects/` en asset_optimizer,
        # lo que dejaba huérfanos al hacer delete_project_r2_assets).
        base_key = f"wcm/projects/{project_id}/visual-diff/{slug}"
        if r2 is None:
            log.warning(
                "visual_diff_r2_not_configured",
                extra={"project_id": project_id, "page_path": page_path},
            )
            return _local_fallback_url(base_key, source_png, target_png, overlay_png)

        try:
            src_url = r2.put_bytes(
                f"{base_key}/source.png",
                source_png,
                content_type="image/png",
                metadata={"project_id": str(project_id), "kind": "source"},
            )
            tgt_url = r2.put_bytes(
                f"{base_key}/target.png",
                target_png,
                content_type="image/png",
                metadata={"project_id": str(project_id), "kind": "target"},
            )
            ovr_url = r2.put_bytes(
                f"{base_key}/overlay.png",
                overlay_png,
                content_type="image/png",
                metadata={"project_id": str(project_id), "kind": "overlay"},
            )
            return src_url, tgt_url, ovr_url
        except Exception as e:  # noqa: BLE001 — R2UploadError u otros
            log.warning(
                "visual_diff_r2_upload_failed",
                extra={"project_id": project_id, "page_path": page_path, "error": str(e)},
            )
            return None, None, None

    def _upsert_visual_diff(
        self,
        ctx: AgentContext,
        *,
        project_id: int,
        page_path: str,
        source_url: str | None,
        target_url: str | None,
        overlay_url: str | None,
        score: float,
    ) -> None:
        """UPSERT en visual_diffs (project_id, page_path) — re-ejecutar
        el agent sobrescribe filas existentes."""
        stmt = (
            pg_insert(VisualDiff)
            .values(
                project_id=project_id,
                page_path=page_path,
                source_screenshot_url=source_url,
                target_screenshot_url=target_url,
                overlay_url=overlay_url,
                score=score,
                viewport_width=DEFAULT_VIEWPORT_WIDTH,
            )
            .on_conflict_do_update(
                constraint="uq_visual_diffs_project_page",
                set_={
                    "source_screenshot_url": source_url,
                    "target_screenshot_url": target_url,
                    "overlay_url": overlay_url,
                    "score": score,
                    "viewport_width": DEFAULT_VIEWPORT_WIDTH,
                },
            )
        )
        ctx.session.execute(stmt)


def _extract_path(url: str) -> str:
    """`https://barpepe.es/contacto` → `/contacto`. Root → `/`."""
    parsed = urlparse(url)
    return parsed.path or "/"


def _build_target_url(target_domain: str, path: str) -> str:
    """`barpepe.es` + `/contacto` → `https://barpepe.es/contacto`. Si
    `target_domain` ya incluye protocolo, se respeta."""
    if target_domain.startswith(("http://", "https://")):
        base = target_domain.rstrip("/")
    else:
        base = f"https://{target_domain.rstrip('/')}"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _slugify(path: str) -> str:
    """`/blog/post-1` → `blog-post-1`. Root → `root`."""
    if path in ("", "/"):
        return "root"
    s = path.strip("/").replace("/", "-")
    # caracteres seguros para R2 key.
    return "".join(c if c.isalnum() or c == "-" else "_" for c in s) or "root"


def _local_fallback_url(
    base_key: str,
    source_png: bytes,
    target_png: bytes,
    overlay_png: bytes,
) -> tuple[str, str, str]:
    """Escribe los 3 PNG a /tmp/wcm-visual-diff/... y devuelve URLs `file://`.

    Sin R2 configurado, el dashboard no puede mostrarlos pero al
    menos quedan accesibles localmente para debug.
    """
    import os
    import tempfile

    root = os.path.join(tempfile.gettempdir(), "wcm-visual-diff", base_key)
    os.makedirs(root, exist_ok=True)
    src_path = os.path.join(root, "source.png")
    tgt_path = os.path.join(root, "target.png")
    ovr_path = os.path.join(root, "overlay.png")
    with open(src_path, "wb") as f:
        f.write(source_png)
    with open(tgt_path, "wb") as f:
        f.write(target_png)
    with open(ovr_path, "wb") as f:
        f.write(overlay_png)
    return f"file://{src_path}", f"file://{tgt_path}", f"file://{ovr_path}"
