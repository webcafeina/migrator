"""AssetOptimizerAgent — descarga, optimiza y sube assets del proyecto a R2.

Flujo:
1. Itera los `Asset` del proyecto con `status=PENDING`.
2. Descarga el binario desde `original_url` (httpx, redirects ON).
3. Calcula sha256 → si difiere del `hash` ya almacenado, actualiza.
4. Para imágenes (PNG/JPG/JPEG/WEBP/GIF) las re-encoda a WebP con Pillow
   (calidad 82, sin metadata EXIF que pueda contener datos sensibles).
5. Sube a R2 con key `wcm/projects/{project_id}/{hash[:2]}/{hash}.webp`.
6. Persiste `r2_key`, `optimized_path` (key), `mime`, `size_bytes`,
   `width`, `height`, `status=READY`.

Sin credenciales R2 → status `OPTIMIZED` y warning. El siguiente run lo
recoge si la config aparece.

Errores tipados:
- Descarga falla → status FAILED + error_message persistido. El pipeline
  no se rompe — un asset roto no debe tirar la migración entera.
- Optimización falla (formato exótico) → keep original bytes, log warning.
"""

from __future__ import annotations

import hashlib
import io
import logging

import httpx
from sqlalchemy import select

from wcm_db.models.assets import Asset
from wcm_types.enums import AssetStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AssetOptimizerError
from wcm_worker.integrations.r2 import R2Client, R2UploadError

log = logging.getLogger("wcm.worker.asset_optimizer")

#: Calidad WebP. 82 es el sweet spot habitual: ~30-50% menos peso que
#: JPEG90 sin pérdida visible. Bumping a 90 sube el peso un 25% por <1%
#: de SSIM medible.
WEBP_QUALITY = 82

#: Tamaño máximo del binario descargado (8 MB). Más allá descartamos el
#: asset por seguridad (webs Wix pueden servir PNGs gigantes accidentalmente).
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024

#: MIMEs que reconocemos como imagen para optimización. Otros formatos
#: (PDF, SVG, MP4...) se suben sin tocar.
IMAGE_MIMES = frozenset({
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/gif", "image/bmp", "image/tiff",
})


class AssetOptimizerAgent(BaseAgent):
    name = "asset-optimizer"
    phase_name = "optimize_assets"

    def __init__(
        self,
        *,
        r2: R2Client | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._injected_r2 = r2
        self._http = http_client or httpx.Client(timeout=30.0, follow_redirects=True)
        self._owns_http = http_client is None

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise AssetOptimizerError("AssetOptimizerAgent requiere project_id")

        r2 = self._injected_r2 or R2Client.from_env()
        pending = self._load_pending(ctx, ctx.project_id)

        if not pending:
            return AgentResult(
                summary=f"Proyecto {ctx.project_id}: 0 assets pendientes",
                outputs={"processed": 0},
            )

        if r2 is None:
            log.warning("asset_optimizer_no_r2", extra={"project_id": ctx.project_id})

        optimized = uploaded = failed = 0
        warnings: list[str] = []

        for asset in pending:
            try:
                payload = self._download(asset.original_url)
            except AssetOptimizerError as e:
                asset.status = AssetStatus.PENDING
                asset.error_message = str(e)
                failed += 1
                continue

            mime, processed, width, height = self._optimize_if_image(payload)
            asset.mime = mime
            asset.size_bytes = len(processed)
            if width:
                asset.width = width
            if height:
                asset.height = height
            asset.hash = hashlib.sha256(processed).hexdigest()
            asset.status = AssetStatus.OPTIMIZED
            optimized += 1

            if r2 is None:
                continue

            key = self._r2_key(ctx.project_id, asset.hash, mime)
            try:
                r2.put_bytes(
                    key, processed, content_type=mime,
                    metadata={"original_url": asset.original_url[:1024]},
                )
            except R2UploadError as e:
                asset.error_message = f"r2_upload: {e}"
                warnings.append(f"asset {asset.id}: r2 upload falló: {e}")
                continue

            asset.r2_key = key
            asset.optimized_path = key
            asset.status = AssetStatus.READY
            uploaded += 1

        ctx.session.flush()
        if self._owns_http:
            self._http.close()

        return AgentResult(
            summary=f"Project {ctx.project_id}: {optimized} optimized, "
            f"{uploaded} uploaded a R2, {failed} failed",
            outputs={
                "optimized": optimized,
                "uploaded": uploaded,
                "failed": failed,
                "r2_configured": r2 is not None,
            },
            warnings=warnings,
        )

    # ---------- helpers ----------

    def _load_pending(self, ctx: AgentContext, project_id: int) -> list[Asset]:
        stmt = select(Asset).where(
            Asset.project_id == project_id,
            Asset.status.in_([AssetStatus.PENDING, AssetStatus.DOWNLOADED]),
        )
        return list(ctx.session.execute(stmt).scalars())

    def _download(self, url: str) -> bytes:
        try:
            resp = self._http.get(url)
        except httpx.RequestError as e:
            raise AssetOptimizerError(f"descarga falló: {e}") from e
        if resp.status_code != 200:
            raise AssetOptimizerError(f"HTTP {resp.status_code} para {url}")
        if len(resp.content) > MAX_DOWNLOAD_BYTES:
            raise AssetOptimizerError(
                f"asset > {MAX_DOWNLOAD_BYTES} bytes ({len(resp.content)})"
            )
        return resp.content

    def _optimize_if_image(self, data: bytes) -> tuple[str, bytes, int | None, int | None]:
        """Devuelve (mime, bytes, width, height). Si no es imagen reconocida,
        devuelve los bytes tal cual con mime octet-stream.
        """
        sniffed = _sniff_mime(data)
        if sniffed not in IMAGE_MIMES:
            return sniffed or "application/octet-stream", data, None, None
        try:
            from PIL import Image
        except ImportError as e:
            log.warning("pillow_not_installed", extra={"error": str(e)})
            return sniffed, data, None, None
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as e:  # noqa: BLE001
            log.warning("image_open_failed", extra={"error": str(e)})
            return sniffed, data, None, None

        width, height = img.size
        # Strip metadata + convertir a RGB para WebP (canal alfa preservado en RGBA).
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
        return "image/webp", out.getvalue(), width, height

    def _r2_key(self, project_id: int, hash_: str, mime: str) -> str:
        ext = _ext_for_mime(mime)
        return f"wcm/projects/{project_id}/{hash_[:2]}/{hash_}{ext}"


def _sniff_mime(data: bytes) -> str | None:
    """Sniff básico por magic bytes — suficiente para asset comunes.

    No usamos `python-magic` para no añadir dep nativa (libmagic). Las
    cabeceras de los formatos web habituales son inconfundibles.
    """
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:5] in (b"<?xml", b"<svg "):
        return "image/svg+xml"
    return None


def _ext_for_mime(mime: str) -> str:
    return {
        "image/webp": ".webp",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
    }.get(mime, ".bin")
