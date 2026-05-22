"""AssetUploaderAgent — sube assets de R2 al WP media library destino.

Sprint v0.24.0 — Bloque A.

Flujo:
1. Carga `Asset` del proyecto con `status=READY`, `wp_attachment_id IS NULL`,
   `mime LIKE 'image/%'` o `'video/%'`.
2. Por cada uno:
   - Descarga binario de R2 vía `R2Client.get_bytes(r2_key)`.
   - Escribe a `/tmp/wcm-{project_id}-{asset_id}.{ext}`.
   - Sube a WP REST `POST /wp/v2/media` con `WpRestClient.upload_media(path, alt_text)`.
   - Persiste `wp_attachment_id`, `wp_source_url`, `wp_media_uploaded_at`.
   - Borra archivo temporal.
3. Tras todos los uploads exitosos, reescribe URLs en `bricks_pages.bricks_json`:
   - Reemplaza `/wp-content/uploads/placeholder-asset-{id}.webp` por la URL real.
   - Añade `image.id` con el `wp_attachment_id`.
4. Idempotente: re-runs salta assets con `wp_media_uploaded_at IS NOT NULL`.

Sin credenciales WP destino o R2 → SKIPPED. El fallback de v0.23.0 (resolver
con URL placeholder) ya cubre el caso degradado sin romper el pipeline.

Errores tipados:
- `AssetUploaderError(blocks_pipeline=False)` — N fallos consecutivos
  abortan la fase pero NO el pipeline. El destino renderiza con URLs
  placeholder hasta re-run.
- Idempotente por idempotence_key = (project_id, asset_id) ya que el
  modelo persiste `wp_media_uploaded_at`.

Limitaciones MVP v0.24.0:
- No sube `font/*` ni `application/*` — solo image+video. Fonts siguen
  el approach actual del checklist (operator instala manualmente).
- Rate-limit suave: 2s entre uploads si destino devuelve 429.
- Concurrency=3 (límite suave para no saturar el WP destino).
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from wcm_db.models.assets import Asset
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_types.enums import AssetStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AssetUploaderError
from wcm_worker.integrations.r2 import R2Client, R2UploadError
from wcm_wp_client.config import WpClientConfig
from wcm_wp_client.errors import WpRestError
from wcm_wp_client.rest import WpRestClient

log = logging.getLogger("wcm.worker.asset_uploader")

#: Concurrencia de uploads simultáneos. Bajo para no saturar WP destino
#: en shared hostings (cPanel limita 5-10 conexiones PHP en paralelo).
DEFAULT_CONCURRENCY = 3

#: Pausa entre uploads tras un 429 (WP rate-limited).
RATE_LIMIT_PAUSE_S = 2.0

#: Máximo de fallos consecutivos antes de abortar la fase.
MAX_CONSECUTIVE_FAILURES = 5

#: MIMEs que subimos al WP media library. Otros (fonts, application/...)
#: quedan como residual del checklist.
UPLOADABLE_MIME_PREFIXES = ("image/", "video/")


def _resolve_concurrency() -> int:
    """`WCM_ASSET_UPLOADER_CONCURRENCY` env override, clamp [1, 10]."""
    raw = os.environ.get("WCM_ASSET_UPLOADER_CONCURRENCY", "")
    try:
        v = int(raw)
    except ValueError:
        return DEFAULT_CONCURRENCY
    if v < 1 or v > 10:
        return DEFAULT_CONCURRENCY
    return v


def _ext_from_mime(mime: str) -> str:
    """`image/webp` → `.webp`. Conservador: si no reconoce, `.bin`."""
    mime_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }
    return mime_map.get(mime, ".bin")


class AssetUploaderAgent(BaseAgent):
    name = "asset-uploader"
    phase_name = "asset_uploader"

    def __init__(
        self,
        *,
        r2: R2Client | None = None,
        wp_rest: WpRestClient | None = None,
    ) -> None:
        self._injected_r2 = r2
        self._injected_rest = wp_rest

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise AssetUploaderError("AssetUploaderAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise AssetUploaderError(f"Project {ctx.project_id} no existe")

        r2 = self._injected_r2 or R2Client.from_env()
        if r2 is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin credenciales R2 — "
                    "asset_uploader SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_r2"},
                warnings=["R2_* env vars no configuradas"],
            )

        rest = self._injected_rest or self._build_rest_from_project(project)
        if rest is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin credenciales WP REST — "
                    "asset_uploader SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_wp_rest"},
                warnings=["WP_DEFAULT_REST_* env vars no configuradas"],
            )

        candidates = self._load_candidates(ctx, project.id)
        if not candidates:
            return AgentResult(
                summary=(
                    f"Project {project.id}: 0 assets pendientes de subir a WP"
                ),
                outputs={"uploaded": 0, "skipped_already_uploaded": 0},
            )

        outcome = asyncio.run(
            self._run_uploads(ctx=ctx, r2=r2, rest=rest, candidates=candidates)
        )
        # Tras subir, reescribir URLs en bricks_pages.
        rewritten_pages = self._rewrite_bricks_pages_urls(ctx, project.id)

        ctx.session.flush()
        return AgentResult(
            summary=(
                f"Project {project.id}: "
                f"{outcome['uploaded']} subidos, "
                f"{outcome['failed']} fallidos, "
                f"{rewritten_pages} bricks_pages reescritas"
            ),
            outputs={
                "uploaded": outcome["uploaded"],
                "failed": outcome["failed"],
                "skipped_already_uploaded": outcome["skipped"],
                "rewritten_pages": rewritten_pages,
                "aborted_consecutive_failures": outcome.get("aborted", False),
            },
            warnings=outcome.get("warnings", []),
        )

    # ---------- helpers ----------

    def _load_candidates(
        self, ctx: AgentContext, project_id: int
    ) -> list[Asset]:
        """Assets candidatos: READY + sin wp_attachment_id + mime
        uploadable. Excluye los ya subidos (idempotencia)."""
        stmt = (
            select(Asset)
            .where(
                Asset.project_id == project_id,
                Asset.status == AssetStatus.READY,
                Asset.r2_key.is_not(None),
                Asset.wp_attachment_id.is_(None),
            )
            .order_by(Asset.id.asc())
        )
        all_ready = list(ctx.session.execute(stmt).scalars())
        return [
            a for a in all_ready
            if a.mime and any(a.mime.startswith(p) for p in UPLOADABLE_MIME_PREFIXES)
        ]

    def _build_rest_from_project(
        self, project: Project
    ) -> WpRestClient | None:
        """Construye WpRestClient desde env defaults (WP_DEFAULT_*).

        Si las vars no están seteadas, `from_env()` lanza ValueError y
        devolvemos None para que el caller marque SKIPPED.

        Para proyectos con credenciales propias (no defaults), habrá
        que descifrar Fernet — fuera del scope MVP, se hace en wp_deployer.
        """
        try:
            cfg = WpClientConfig.from_env()
        except (ValueError, KeyError):
            return None
        return WpRestClient(cfg)

    async def _run_uploads(
        self,
        *,
        ctx: AgentContext,
        r2: R2Client,
        rest: WpRestClient,
        candidates: list[Asset],
    ) -> dict[str, Any]:
        """Wrapper que entra al async context del rest client si no
        está ya abierto, y delega a `_upload_all`."""
        # Si lo construimos nosotros, hay que abrir+cerrar el context.
        # Si lo inyectó el caller (test), asumimos ya inicializado.
        if self._injected_rest is None:
            async with rest:
                return await self._upload_all(
                    ctx=ctx, r2=r2, rest=rest, candidates=candidates
                )
        return await self._upload_all(
            ctx=ctx, r2=r2, rest=rest, candidates=candidates
        )

    async def _upload_all(
        self,
        *,
        ctx: AgentContext,
        r2: R2Client,
        rest: WpRestClient,
        candidates: list[Asset],
    ) -> dict[str, Any]:
        """Sube candidatos con concurrency limitada + tracking
        consecutive_failures para abortar antes de saturar."""
        concurrency = _resolve_concurrency()
        sem = asyncio.Semaphore(concurrency)

        uploaded = 0
        failed = 0
        skipped = 0
        consecutive_failures = 0
        warnings: list[str] = []
        aborted = False

        async def _one(asset: Asset) -> str:
            nonlocal uploaded, failed, skipped, consecutive_failures
            async with sem:
                if asset.wp_media_uploaded_at is not None:
                    skipped += 1
                    return "skipped"
                outcome = await self._upload_single(
                    asset=asset, r2=r2, rest=rest
                )
                if outcome == "uploaded":
                    uploaded += 1
                    consecutive_failures = 0
                elif outcome == "rate_limited":
                    failed += 1
                    consecutive_failures += 1
                    await asyncio.sleep(RATE_LIMIT_PAUSE_S)
                else:
                    failed += 1
                    consecutive_failures += 1
                return outcome

        # Procesar en batches respetando consecutive_failures.
        for asset in candidates:
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                warnings.append(
                    f"asset_uploader: abortado tras {consecutive_failures} "
                    "fallos consecutivos. Re-run cuando el destino esté "
                    "estable."
                )
                aborted = True
                break
            await _one(asset)

        return {
            "uploaded": uploaded,
            "failed": failed,
            "skipped": skipped,
            "aborted": aborted,
            "warnings": warnings,
        }

    async def _upload_single(
        self,
        *,
        asset: Asset,
        r2: R2Client,
        rest: WpRestClient,
    ) -> str:
        """Devuelve `uploaded`/`rate_limited`/`failed`/`r2_missing`."""
        # 1) Descargar R2.
        try:
            data = r2.get_bytes(asset.r2_key)
        except R2UploadError as e:
            log.warning(
                "asset_uploader_r2_get_failed",
                extra={"asset_id": asset.id, "key": asset.r2_key, "error": str(e)[:200]},
            )
            return "r2_missing"

        # 2) Escribir tmp + subir REST.
        ext = _ext_from_mime(asset.mime or "")
        with tempfile.NamedTemporaryFile(
            prefix=f"wcm-{asset.project_id}-{asset.id}-",
            suffix=ext,
            delete=False,
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        try:
            attachment = await rest.upload_media(
                tmp_path,
                alt_text=asset.alt_text or None,
                title=None,
            )
        except WpRestError as e:
            msg = str(e).lower()
            log.warning(
                "asset_uploader_wp_upload_failed",
                extra={"asset_id": asset.id, "error": str(e)[:200]},
            )
            if "429" in msg or "rate" in msg or "too many" in msg:
                tmp_path.unlink(missing_ok=True)
                return "rate_limited"
            tmp_path.unlink(missing_ok=True)
            return "failed"
        finally:
            tmp_path.unlink(missing_ok=True)

        # 3) Persistir attachment_id + source_url.
        asset.wp_attachment_id = int(attachment.get("id", 0)) or None
        asset.wp_source_url = attachment.get("source_url") or attachment.get("guid", {}).get("rendered")
        asset.wp_media_uploaded_at = datetime.now(UTC)
        return "uploaded"

    def _rewrite_bricks_pages_urls(
        self, ctx: AgentContext, project_id: int
    ) -> int:
        """Para cada `bricks_pages.bricks_json` del proyecto, reescribe
        URLs placeholder `/wp-content/uploads/placeholder-asset-{id}.webp`
        por la URL real `wp_source_url`. Mutate-in-place el JSON.

        Devuelve número de páginas con al menos 1 reescritura.
        """
        # Cargar todos los assets con wp_source_url para construir mapping
        # asset_id → {url, id}.
        assets_stmt = select(Asset).where(
            Asset.project_id == project_id,
            Asset.wp_attachment_id.is_not(None),
        )
        url_by_asset_id: dict[int, tuple[int, str]] = {}
        for a in ctx.session.execute(assets_stmt).scalars():
            if a.wp_source_url:
                url_by_asset_id[a.id] = (a.wp_attachment_id, a.wp_source_url)
        if not url_by_asset_id:
            return 0

        pages_stmt = select(BricksPage).where(BricksPage.project_id == project_id)
        rewritten = 0
        for bp in ctx.session.execute(pages_stmt).scalars():
            if not bp.bricks_json:
                continue
            changed = self._rewrite_json_in_place(bp.bricks_json, url_by_asset_id)
            if changed:
                # SQLAlchemy detecta cambio en JSONB mutable solo si
                # flag_modified o reasignación. Reasignamos.
                bp.bricks_json = bp.bricks_json
                ctx.session.add(bp)
                rewritten += 1
        return rewritten

    @staticmethod
    def _rewrite_json_in_place(
        json_obj: Any,
        url_by_asset_id: dict[int, tuple[int, str]],
    ) -> bool:
        """Recorre `json_obj` recursivamente y reescribe URLs placeholder.

        Patrón: cualquier value tipo str que matchee
        `/wp-content/uploads/placeholder-asset-{N}.webp` se reemplaza por
        la URL real. Si el contenedor del string tiene una key adyacente
        `id: null` o falta `id`, también la rellena con el attachment_id.

        Devuelve True si hubo al menos 1 reescritura.
        """
        import re

        pattern = re.compile(
            r"/wp-content/uploads/placeholder-asset-(\d+)\.webp"
        )
        changed = False

        def _walk(node: Any) -> None:
            nonlocal changed
            if isinstance(node, dict):
                # Reescribir url y poner id si existe el placeholder.
                if "url" in node and isinstance(node["url"], str):
                    m = pattern.search(node["url"])
                    if m:
                        aid = int(m.group(1))
                        if aid in url_by_asset_id:
                            attachment_id, new_url = url_by_asset_id[aid]
                            node["url"] = new_url
                            node["id"] = attachment_id
                            changed = True
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        _walk(v)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(json_obj)
        return changed
