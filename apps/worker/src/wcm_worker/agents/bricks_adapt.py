"""BricksAdaptAgent — v0.28.0 fase pipeline `bricks_adapt`.

Recorre todos los `bricks_pages` del proyecto y aplica el adapter
determinista `wcm_bricks_transpiler.adapt_to_bricks_native` para
transformar el JSON semántico producido por el LLM al shape verbatim
que Bricks 2.1.4 consume:

- `_typography.font_size` → `_typography.font-size` (snake → kebab)
- `_padding: "4rem"` → `{top, right, bottom, left}` (string → objeto)
- `color: "#abc"` → `{hex: "#abc"}` (string → objeto)
- `image: "<url>"` → `{url, id?, external?, filename?}` (string → objeto)
- `image.url` que coincide con un asset subido → inyecta `id` WP

Posición en pipeline: DESPUÉS de `asset_uploader` (necesita los
`wp_attachment_id` ya poblados) y ANTES de `pre_deploy_snapshot` /
`deploy_wp` (para que el WP destino reciba JSON ya en shape correcto).

Sin esta fase, el frontend WP renderiza con CSS default (texto plano
sobre fondo blanco) porque Bricks ignora silenciosamente las keys
mal-tipadas. Este es el bug raíz del E2E v0.27.0 (Mariya Design).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from wcm_bricks_transpiler import adapt_to_bricks_native
from wcm_bricks_transpiler.bricks_adapter import AdapterStats
from wcm_db.models.assets import Asset
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent

log = logging.getLogger("wcm.worker.bricks_adapt")


class BricksAdaptAgent(BaseAgent):
    name = "bricks-adapt"
    phase_name = "bricks_adapt"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            return AgentResult(
                summary="BricksAdaptAgent requiere project_id — SKIPPED",
                outputs={"skipped": True, "reason": "no_project_id"},
            )

        pages = ctx.session.execute(
            select(BricksPage).where(BricksPage.project_id == ctx.project_id)
        ).scalars().all()
        if not pages:
            return AgentResult(
                summary=f"Project {ctx.project_id}: 0 bricks_pages — SKIPPED",
                outputs={"skipped": True, "reason": "no_pages"},
            )

        wp_asset_map = self._build_wp_asset_map(ctx)
        valid_class_ids = self._build_valid_class_ids(ctx)
        log.info(
            "bricks_adapt_start project_id=%s pages=%s wp_assets=%s valid_classes=%s",
            ctx.project_id, len(pages), len(wp_asset_map),
            len(valid_class_ids) if valid_class_ids is not None else "all",
        )

        total_stats = AdapterStats()
        pages_modified = 0
        for bp in pages:
            content = bp.bricks_json
            if not isinstance(content, list):
                continue
            stats = AdapterStats()
            new_content = adapt_to_bricks_native(
                content, wp_asset_map=wp_asset_map,
                valid_class_ids=valid_class_ids, stats=stats,
            )
            if stats.total() > 0:
                bp.bricks_json = new_content
                flag_modified(bp, "bricks_json")
                pages_modified += 1
                for k in AdapterStats.__slots__:
                    setattr(total_stats, k, getattr(total_stats, k) + getattr(stats, k))
                log.info(
                    "bricks_adapt_page slug=%s fixes=%s",
                    bp.slug, stats.as_dict(),
                )

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {ctx.project_id}: bricks_adapt "
                f"{pages_modified}/{len(pages)} pages · "
                f"{total_stats.total()} fixes aplicados"
            ),
            outputs={
                "pages_total": len(pages),
                "pages_modified": pages_modified,
                "fixes_total": total_stats.total(),
                "fixes_breakdown": total_stats.as_dict(),
                "wp_assets_in_map": len(wp_asset_map),
            },
        )

    @staticmethod
    def _build_valid_class_ids(ctx: AgentContext) -> set[str] | None:
        """Devuelve el set de IDs de Global Classes válidas desde
        `Project.bricks_global_classes`. None si el proyecto no tiene
        catálogo todavía → adapter no filtra (legacy behavior)."""
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            return None
        classes = project.bricks_global_classes or []
        if not classes:
            return None
        return {c["id"] for c in classes if isinstance(c, dict) and "id" in c}

    @staticmethod
    def _build_wp_asset_map(ctx: AgentContext) -> dict[str, dict]:
        """Construye dict URL → wp_data para asset_uploader-completed assets.

        Mapea AMBAS URLs (origin Wix `original_url` + WP final `wp_source_url`)
        al mismo `wp_data` para cubrir bricks_json donde el LLM dejó URLs
        del origen Y casos donde asset_uploader ya las reescribió.
        """
        assets = ctx.session.execute(
            select(Asset).where(
                Asset.project_id == ctx.project_id,
                Asset.wp_attachment_id.is_not(None),
            )
        ).scalars().all()
        mapping: dict[str, dict] = {}
        for a in assets:
            filename = (a.original_url or "").rsplit("/", 1)[-1] or "asset"
            wp_data = {
                "id": a.wp_attachment_id,
                "filename": filename,
                "size": "large",
                "url": a.wp_source_url or a.original_url,
                "full": a.wp_source_url or a.original_url,
            }
            if a.original_url:
                mapping[a.original_url] = wp_data
            if a.wp_source_url and a.wp_source_url != a.original_url:
                mapping[a.wp_source_url] = wp_data
        return mapping
