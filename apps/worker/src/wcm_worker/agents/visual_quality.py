"""VisualQualityAgent — gate final de render (v0.28.0 B6).

Tras `deploy_wp` + `preview_thumbnails`, abre cada page WP con Playwright
y lee `getComputedStyle` de elementos clave (h1, section, img) para
detectar si el frontend renderizó con los Bricks Theme Styles o cayó al
CSS default WordPress (texto plano sobre fondo blanco — bug raíz del
E2E v0.27.0 Mariya Design).

Diseño:
- Sin Playwright instalado → SKIPPED + warning (no bloquea pipeline).
- Sin WP_DEFAULT_* config → SKIPPED.
- Score por página `0.0–1.0` basado en 4 señales determinísticas (sin AI).
- Score < threshold (default `0.60`) → residual `BLOCKING_GO_LIVE` con
  detalle de qué señales fallaron.
- Ratio global `pages_ok / pages_total`: si < 0.60, warning crítico
  pero NO marca qa_failed por sí solo (eso es decisión del operador
  tras revisar las residuals).

Threshold ajustable vía env `WCM_VISUAL_QUALITY_THRESHOLD` (float 0-1).
Threshold por defecto: 0.60.

Las 4 señales (sumadas — pesos a 0.30/0.30/0.20/0.20):
1. **Bricks root presente**: `.brx-body`, `.brxe-section`, `[class*="brxe-"]`.
2. **h1 con tamaño explícito ≥24px** (no default `2em`/`32px` heredado).
3. **h1 SIN font-family Times/serif default** (señal directa de tema cargado).
4. **section con padding ≥16px** (theme styles aplicaron `_padding`).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent

log = logging.getLogger("wcm.worker.visual_quality")

#: Threshold por página: score mínimo aceptable. Override via env.
DEFAULT_QUALITY_THRESHOLD = 0.60
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
DEFAULT_TIMEOUT_S = 30.0


#: Script JS que se inyecta en cada page tras `goto`. Lee computed styles
#: y devuelve un dict con counters. Sin AI — todo numérico/booleano.
_QUALITY_PROBE_JS = """\
() => {
    const h1s = Array.from(document.querySelectorAll('h1'));
    const sections = Array.from(document.querySelectorAll(
        'section, .brxe-section, [class*="brxe-section"]'
    ));
    const result = {
        h1_count: h1s.length,
        h1_default_font: 0,
        h1_with_explicit_size: 0,
        section_count: sections.length,
        section_with_padding: 0,
        has_bricks_root: !!document.querySelector(
            '.brx-body, .brxe-section, [class*="brxe-"]'
        ),
    };
    h1s.forEach((h) => {
        const cs = window.getComputedStyle(h);
        const ff = (cs.fontFamily || '').toLowerCase();
        if (
            !ff
            || ff === 'serif'
            || ff.includes('times')
            || (ff.includes('serif') && !ff.includes('sans-serif'))
        ) {
            result.h1_default_font += 1;
        }
        if (parseFloat(cs.fontSize || '0') >= 24) {
            result.h1_with_explicit_size += 1;
        }
    });
    sections.forEach((s) => {
        const cs = window.getComputedStyle(s);
        if (
            parseFloat(cs.paddingTop || '0') >= 16
            || parseFloat(cs.paddingBottom || '0') >= 16
        ) {
            result.section_with_padding += 1;
        }
    });
    return result;
}
"""


def score_from_probe(probe: dict[str, Any]) -> tuple[float, list[str]]:
    """Calcula score 0-1 desde el dict del probe + lista de señales fallidas.

    Función pura para tests sin Playwright.
    """
    failed: list[str] = []
    score = 0.0

    # 1. Bricks root presente (0.30)
    if probe.get("has_bricks_root"):
        score += 0.30
    else:
        failed.append("no_bricks_root_class")

    # 2. h1 con tamaño explícito (0.30)
    h1_count = probe.get("h1_count", 0)
    if h1_count == 0:
        failed.append("no_h1_in_page")
    elif probe.get("h1_with_explicit_size", 0) > 0:
        score += 0.30
    else:
        failed.append("h1_default_size")

    # 3. h1 SIN serif por default (0.20)
    if h1_count > 0 and probe.get("h1_default_font", 0) == 0:
        score += 0.20
    elif h1_count > 0:
        failed.append("h1_default_serif_font")

    # 4. Sections con padding (0.20)
    sc = probe.get("section_count", 0)
    sp = probe.get("section_with_padding", 0)
    if sc > 0 and (sp / sc) >= 0.5:
        score += 0.20
    elif sc > 0:
        failed.append("sections_without_padding")
    elif sc == 0:
        failed.append("no_sections_found")

    return round(score, 2), failed


class VisualQualityAgent(BaseAgent):
    name = "visual-quality"
    phase_name = "visual_quality"

    def __init__(
        self,
        *,
        prober: Any | None = None,
        threshold: float | None = None,
    ) -> None:
        """`prober`: callable async `(url, auth) -> dict` inyectable para tests.
        Si None, usa Playwright real.
        """
        self._injected_prober = prober
        self._threshold = (
            threshold
            if threshold is not None
            else float(os.environ.get(
                "WCM_VISUAL_QUALITY_THRESHOLD",
                str(DEFAULT_QUALITY_THRESHOLD),
            ))
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            return AgentResult(
                summary="VisualQualityAgent requiere project_id — SKIPPED",
                outputs={"skipped": True, "reason": "no_project_id"},
            )
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            return AgentResult(
                summary=f"Project {ctx.project_id} no existe — SKIPPED",
                outputs={"skipped": True, "reason": "no_project"},
            )
        pages = ctx.session.execute(
            select(BricksPage).where(
                BricksPage.project_id == ctx.project_id,
                BricksPage.wp_post_id.is_not(None),
            )
        ).scalars().all()
        if not pages:
            return AgentResult(
                summary=f"Project {project.id}: 0 pages con wp_post_id — SKIPPED",
                outputs={"skipped": True, "reason": "no_deployed_pages"},
            )

        target = self._resolve_wp_target()
        if target is None:
            return AgentResult(
                summary="WP destino no configurado — SKIPPED",
                outputs={"skipped": True, "reason": "no_wp_target"},
                warnings=[
                    "Configurar WP_DEFAULT_SITE_URL + REST_USER + "
                    "REST_APP_PASSWORD para activar visual_quality."
                ],
            )

        prober = self._injected_prober or self._default_prober
        outcome = asyncio.run(
            self._check_all(
                ctx=ctx, project=project, pages=pages,
                target=target, prober=prober,
            )
        )
        ctx.session.flush()

        pages_ok = outcome["pages_ok"]
        pages_total = outcome["pages_total"]
        global_ratio = pages_ok / pages_total if pages_total else 0.0
        warnings = outcome["warnings"]
        if global_ratio < self._threshold:
            warnings.append(
                f"⚠️ Visual quality global ratio {global_ratio:.0%} < "
                f"{self._threshold:.0%} — revisar Bricks Theme Styles / "
                f"deployment antes de publicar."
            )

        return AgentResult(
            summary=(
                f"Project {project.id}: visual_quality "
                f"{pages_ok}/{pages_total} pages OK ({global_ratio:.0%}), "
                f"threshold={self._threshold:.0%}"
            ),
            outputs={
                "pages_total": pages_total,
                "pages_ok": pages_ok,
                "pages_failed": outcome["pages_failed"],
                "global_ratio": round(global_ratio, 2),
                "threshold": self._threshold,
                "page_scores": outcome["page_scores"],
            },
            warnings=warnings,
            residual_tasks_created=outcome["residuals_created"],
        )

    # ---------- helpers ----------

    @staticmethod
    def _resolve_wp_target() -> dict[str, str] | None:
        site_url = os.environ.get("WP_DEFAULT_SITE_URL", "").strip().rstrip("/")
        user = os.environ.get("WP_DEFAULT_REST_USER", "").strip()
        pwd = os.environ.get("WP_DEFAULT_REST_APP_PASSWORD", "").strip()
        if not site_url or not user or not pwd:
            return None
        return {
            "site_url": site_url,
            "user": user,
            "app_password": pwd.replace(" ", ""),
        }

    async def _check_all(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        pages: list[BricksPage],
        target: dict[str, str],
        prober: Any,
    ) -> dict[str, Any]:
        pages_ok = 0
        pages_failed = 0
        residuals_created = 0
        warnings: list[str] = []
        page_scores: list[dict[str, Any]] = []

        for bp in pages:
            url = f"{target['site_url']}/?p={bp.wp_post_id}&preview=true"
            try:
                probe = await prober(url, target)
                score, failed_signals = score_from_probe(probe)
                page_scores.append({
                    "slug": bp.slug,
                    "wp_post_id": bp.wp_post_id,
                    "score": score,
                    "failed_signals": failed_signals,
                })
                log.info(
                    "visual_quality_page slug=%s score=%.2f failed=%s",
                    bp.slug, score, failed_signals,
                )
                if score >= self._threshold:
                    pages_ok += 1
                else:
                    pages_failed += 1
                    residuals_created += self._emit_residual(
                        ctx, project, bp, score, failed_signals,
                    )
            except Exception as e:  # noqa: BLE001 — captura todo aquí
                log.warning(
                    "visual_quality_check_failed slug=%s err=%s",
                    bp.slug, str(e)[:200],
                )
                pages_failed += 1
                warnings.append(
                    f"Página '{bp.slug}': probe failed ({str(e)[:80]})"
                )

        return {
            "pages_ok": pages_ok,
            "pages_failed": pages_failed,
            "pages_total": len(pages),
            "residuals_created": residuals_created,
            "warnings": warnings,
            "page_scores": page_scores,
        }

    @staticmethod
    def _emit_residual(
        ctx: AgentContext,
        project: Project,
        bp: BricksPage,
        score: float,
        failed_signals: list[str],
    ) -> int:
        signals_str = ", ".join(failed_signals) or "n/a"
        residual = ResidualTask(
            project_id=project.id,
            title=f"Render Bricks fallido en '{bp.slug}' (score {score:.0%})",
            description=(
                f"La página '{bp.slug}' (wp_post_id={bp.wp_post_id}) renderiza "
                f"sin estilos Bricks aplicados. Señales fallidas: {signals_str}.\n\n"
                "Posibles causas:\n"
                "- Bricks Theme Styles no importados en WP destino.\n"
                "- bricks_json en BD con shape inválido (snake_case keys, "
                "color strings, image planos) que Bricks ignora.\n"
                "- Plugin Bricks no activado o licencia caducada.\n\n"
                "Revisar manualmente y/o relanzar el pipeline si el problema "
                "es transient."
            ),
            category=ResidualCategory.BLOCKING_GO_LIVE,
            status=ResidualStatus.OPEN,
        )
        ctx.session.add(residual)
        return 1

    async def _default_prober(
        self, url: str, target: dict[str, str]
    ) -> dict[str, Any]:
        """Abre `url` con Playwright + http_credentials y ejecuta probe JS."""
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Playwright no instalado. `pip install '.[browser]'` + "
                "`playwright install chromium`."
            ) from e

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={
                        "width": DEFAULT_VIEWPORT_WIDTH,
                        "height": DEFAULT_VIEWPORT_HEIGHT,
                    },
                    http_credentials={
                        "username": target["user"],
                        "password": target["app_password"],
                    },
                    locale="es-ES",
                )
                context.set_default_timeout(int(DEFAULT_TIMEOUT_S * 1000))
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle")
                return await page.evaluate(_QUALITY_PROBE_JS)
            finally:
                await browser.close()
