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
from urllib.parse import urlparse

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
        warnings: list[str] = []
        scores: list[float] = []
        below_threshold: list[tuple[str, float]] = []
        compared = 0
        failed_pages = 0

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

        try:
            with session_cm as session_pw:
                for page in pages:
                    page_path = _extract_path(page.url)
                    target_url = _build_target_url(project.target_domain, page_path)
                    try:
                        source_png = session_pw.capture(page.url)
                        target_png = session_pw.capture(target_url)
                    except Exception as e:  # noqa: BLE001 — Playwright timeout, DNS, etc.
                        failed_pages += 1
                        log.warning(
                            "visual_diff_page_failed",
                            extra={
                                "project_id": project.id,
                                "page_path": page_path,
                                "error": str(e),
                            },
                        )
                        warnings.append(
                            f"Fallo capturando {page_path}: {type(e).__name__}: {str(e)[:120]}"
                        )
                        continue

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
        base_key = f"projects/{project_id}/visual-diff/{slug}"
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
