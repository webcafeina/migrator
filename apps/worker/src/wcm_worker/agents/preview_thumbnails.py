"""PreviewThumbnailsAgent — Playwright screenshots sobre WP draft (v0.26.0 B6).

Fase del pipeline que corre **después** de `wp_deployer` (que deja las
páginas como `draft` en WP destino) y **antes** de `notify`. Para cada
`bricks_pages.wp_post_id` toma una captura con Playwright, la sube a R2
(o local en MVP), y actualiza `BricksPage.preview_thumbnail_url` +
`preview_captured_at`.

El operador ve el thumbnail en `/projects/[id]/preview` (B7) — fidelidad
100% sin Figma (descartado por viabilidad técnica, ver ADR-042).

Sin Playwright instalado → SKIPPED + warning.
Sin `wp_post_id` en BricksPage → skip esa página (no deployada aún).

Errores tipados: `RedesignAgentError(blocks_pipeline=False)`. Fallos
por página → ResidualTask, no bloquean el pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import RedesignAgentError

log = logging.getLogger("wcm.worker.preview_thumbnails")

#: Viewport por defecto del thumbnail. Más ancho que el típico Mobile
#: porque el operador revisa en desktop dashboard. Full-page captura
#: todo el alto.
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
DEFAULT_TIMEOUT_S = 30.0


class PreviewThumbnailsAgent(BaseAgent):
    name = "preview-thumbnails"
    phase_name = "preview_thumbnails"

    def __init__(
        self,
        *,
        screenshotter: Any | None = None,
        uploader: Any | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """`screenshotter` inyectable para tests: callable async
        `(url, auth) -> bytes`. Si None, usa Playwright real.

        `uploader` opcional: callable `(key, png_bytes) -> public_url`.
        Si None, persiste al `output_dir` local y devuelve `file://...`.
        """
        self._injected_screenshotter = screenshotter
        self._injected_uploader = uploader
        self._output_dir = output_dir or Path(
            os.environ.get("WCM_PREVIEW_THUMBS_DIR", "/tmp/wcm-thumbs")
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("PreviewThumbnailsAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")

        # Páginas deployadas (con wp_post_id).
        stmt = select(BricksPage).where(
            BricksPage.project_id == ctx.project_id,
            BricksPage.wp_post_id.is_not(None),
        )
        pages = ctx.session.execute(stmt).scalars().all()
        if not pages:
            return AgentResult(
                summary=(
                    f"Project {project.id}: 0 bricks_pages con wp_post_id "
                    "→ SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_deployed_pages"},
            )

        # Resolver WP destino: site_url + auth.
        target = self._resolve_wp_target(project)
        if target is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: WP destino no configurado → SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_wp_target"},
                warnings=[
                    "Configurar WP_DEFAULT_SITE_URL + WP_DEFAULT_REST_USER + "
                    "WP_DEFAULT_REST_APP_PASSWORD en .env para activar "
                    "thumbnails."
                ],
            )

        outcome = asyncio.run(
            self._capture_all(ctx=ctx, project=project, pages=pages, target=target)
        )

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: thumbnails · "
                f"{outcome['captured']}/{len(pages)} páginas · "
                f"{outcome['failed']} fallidas"
            ),
            outputs={
                "skipped": False,
                "pages_total": len(pages),
                "captured": outcome["captured"],
                "failed": outcome["failed"],
            },
            warnings=outcome.get("warnings", []),
            residual_tasks_created=outcome.get("residuals_created", 0),
        )

    # ---------- helpers ----------

    @staticmethod
    def _resolve_wp_target(project: Project) -> dict[str, str] | None:
        """Lee config WP destino del env (mismo patrón que wp_deployer).

        Devuelve dict `{site_url, user, app_password}` o None si falta
        cualquier pieza obligatoria.
        """
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

    async def _capture_all(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        pages: list[BricksPage],
        target: dict[str, str],
    ) -> dict[str, Any]:
        captured = 0
        failed = 0
        residuals_created = 0
        warnings: list[str] = []

        # Output dir local (siempre se crea, también si subimos a R2 lo
        # usamos como buffer).
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            warnings.append(f"output_dir no creable: {e}")

        screenshotter = (
            self._injected_screenshotter
            or self._default_screenshotter
        )

        for bp in pages:
            url = self._preview_url(target["site_url"], bp.wp_post_id)
            try:
                png_bytes = await screenshotter(url, target)
                public_url = self._persist_png(bp, png_bytes)
                bp.preview_thumbnail_url = public_url
                bp.preview_captured_at = datetime.now(UTC)
                captured += 1
            except Exception as e:  # noqa: BLE001 — captura todo aquí
                log.warning(
                    "preview_thumbnail_failed",
                    extra={
                        "project_id": project.id, "slug": bp.slug,
                        "wp_post_id": bp.wp_post_id, "error": str(e)[:200],
                    },
                )
                failed += 1
                residuals_created += self._emit_residual(
                    ctx, project, bp, str(e)[:200]
                )
                warnings.append(
                    f"Página '{bp.slug}' (wp_post_id={bp.wp_post_id}): "
                    f"{str(e)[:80]}"
                )

        return {
            "captured": captured,
            "failed": failed,
            "warnings": warnings,
            "residuals_created": residuals_created,
        }

    @staticmethod
    def _preview_url(site_url: str, wp_post_id: int) -> str:
        """URL preview de WP (draft o published). Requiere auth para draft.

        Patrón estándar de WP: `?p={id}&preview=true`. Si la página está
        published, también funciona y muestra la versión publicada.
        """
        return f"{site_url}/?p={wp_post_id}&preview=true"

    async def _default_screenshotter(
        self, url: str, target: dict[str, str]
    ) -> bytes:
        """Captura usando Playwright + httpCredentials para Basic Auth.

        Lazy import — Playwright es extra `[browser]`.
        """
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover
            raise RedesignAgentError(
                "Playwright no instalado. Instala con `pip install '.[browser]'` "
                "y `playwright install chromium`."
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
                return await page.screenshot(full_page=True, type="png")
            finally:
                await browser.close()

    def _persist_png(self, bp: BricksPage, png_bytes: bytes) -> str:
        """Sube a R2 si hay uploader, si no guarda local + devuelve file://."""
        key = (
            f"projects/{bp.project_id}/previews/"
            f"{bp.slug.strip('/').replace('/', '_') or 'home'}.png"
        )
        if self._injected_uploader is not None:
            return self._injected_uploader(key, png_bytes)
        # Local fallback (modo dev sin R2).
        local_path = self._output_dir / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(png_bytes)
        return f"file://{local_path.resolve()}"

    @staticmethod
    def _emit_residual(
        ctx: AgentContext,
        project: Project,
        bp: BricksPage,
        error_msg: str,
    ) -> int:
        task = ResidualTask(
            project_id=project.id,
            title=(
                f"Thumbnail preview falló — página '{bp.slug}' "
                f"(wp_post_id={bp.wp_post_id})"
            ),
            description=(
                f"Playwright no pudo capturar el preview WP. "
                f"Error: {error_msg}. "
                "Verificar credenciales WP_DEFAULT_REST_USER + APP_PASSWORD "
                "o capturar manualmente."
            ),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=5,
            screenshot_paths=[],
            status=ResidualStatus.OPEN,
            generated_by="preview_thumbnails",
        )
        ctx.session.add(task)
        return 1
