"""RedesignImagesAgent — generación de imágenes con gpt-image-2 (v0.26.0 B5).

Fase del pipeline que rellena slots de imagen vacíos en el Brief usando
gpt-image-2 (OpenAI image model, abril 2026).

Cuándo corre:
- `Project.brief_json` está poblado (BriefGenerator pasó).
- Hay al menos una `Brief.pages[i].sections[j]` con `asset_id is None` Y
  el tipo de sección admite imagen (hero, image, gallery, testimonial).

Flujo:
1. Itera secciones con `image_slot==True` (heurística por type) y
   `asset_id is None`.
2. Para cada slot vacío:
   - Construye prompt determinista desde el Brief (business + brand
     + intent + tone_of_voice).
   - Llama `OpenAIClient.generate_image(prompt, quality, size)`.
   - Sube PNG a R2 (asset_optimizer ya configurado).
   - Crea fila `Asset` con r2_key + alt_text + cost en sizes_json.
   - Actualiza `Brief.pages[i].sections[j].asset_id` con el nuevo id
     + adjunta `ai_image_metadata` (prompt + model + cost + ts).
3. Budget tracking: si el coste acumulado supera
   `Project.image_generation_budget_usd`, para y emite ResidualTask
   "X slots quedaron sin imagen, generación detenida por budget".

Errores tipados: `RedesignAgentError(blocks_pipeline=False)`. Si la
generación falla en una sección, el slot queda NULL y emite
ResidualTask "imagen no generada para X" sin abortar el pipeline.

Sin `OPENAI_API_KEY` → SKIPPED + warning.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from wcm_db.models.assets import Asset
from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import (
    AssetStatus,
    ResidualCategory,
    ResidualStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import (
    OpenAIClientError,
    RedesignAgentError,
)
from wcm_worker.integrations.openai_client import (
    OpenAIClient,
    OpenAIImageResult,
)

log = logging.getLogger("wcm.worker.redesign_images")

#: Tipos de sección que aceptan imagen (rellenable por gpt-image-2).
#: Los demás (text, faq, pricing, form, cta puro) se ignoran.
_IMAGE_SECTION_TYPES = frozenset(
    {"hero", "image", "gallery", "testimonial", "ai_generated"}
)

#: Tipo → (quality, size) por defecto. Hero usa formato vertical para
#: backgrounds; el resto cuadrado para decoración. quality medium es
#: el sweet spot (~$0.05/imagen vs $0.21 high).
_TYPE_TO_IMAGE_PARAMS: dict[str, tuple[str, str]] = {
    "hero": ("medium", "1536x1024"),
    "image": ("medium", "1024x1024"),
    "gallery": ("medium", "1024x1024"),
    "testimonial": ("medium", "1024x1024"),
    "ai_generated": ("medium", "1024x1024"),
}


class RedesignImagesAgent(BaseAgent):
    name = "redesign-images"
    phase_name = "redesign_images"

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
        r2_uploader: Any | None = None,
    ) -> None:
        """`openai_client` inyectable para tests. `r2_uploader` también
        (objeto con `.upload_bytes(key, data, content_type) -> str`).
        Si None, las imágenes se guardan localmente en `data_dir` (modo
        dev sin R2).
        """
        self._injected_client = openai_client
        self._injected_uploader = r2_uploader

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise RedesignAgentError("RedesignImagesAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise RedesignAgentError(f"Project {ctx.project_id} no existe")

        brief = project.brief_json
        if not brief or not brief.get("pages"):
            return AgentResult(
                summary=f"Project {project.id}: sin brief_json → SKIPPED",
                outputs={"skipped": True, "reason": "no_brief"},
            )

        empty_slots = self._find_empty_image_slots(brief)
        if not empty_slots:
            return AgentResult(
                summary=(
                    f"Project {project.id}: 0 slots vacíos → SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_empty_slots"},
            )

        client = self._injected_client or OpenAIClient.from_env()
        if client is None:
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin OPENAI_API_KEY → "
                    "redesign_images SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_openai_key"},
                warnings=[
                    "Configurar OPENAI_API_KEY para activar generación de imágenes."
                ],
            )

        budget = self._resolve_budget(project)

        outcome = asyncio.run(
            self._process_slots(
                ctx=ctx, project=project, brief=brief, client=client,
                empty_slots=empty_slots, budget_usd=budget,
            )
        )

        # Marca brief_json como modificado para que SQLAlchemy lo persista.
        flag_modified(project, "brief_json")
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: image generation · "
                f"{outcome['images_generated']}/{outcome['slots_total']} "
                f"slots rellenos · "
                f"coste ${outcome['cost_total']:.4f} / "
                f"${budget:.2f} budget"
            ),
            outputs={
                "skipped": False,
                "slots_total": outcome["slots_total"],
                "images_generated": outcome["images_generated"],
                "images_failed": outcome["images_failed"],
                "cost_usd_total": outcome["cost_total"],
                "budget_usd": float(budget),
                "budget_exhausted": outcome["budget_exhausted"],
            },
            warnings=outcome.get("warnings", []),
            residual_tasks_created=outcome["residuals_created"],
        )

    # ---------- helpers ----------

    @staticmethod
    def _find_empty_image_slots(
        brief: dict[str, Any],
    ) -> list[tuple[int, int, str]]:
        """Devuelve lista de `(page_index, section_index, section_type)`
        para secciones con asset_id NULL y tipo image-capable."""
        slots: list[tuple[int, int, str]] = []
        for page_idx, page in enumerate(brief.get("pages") or []):
            for sec_idx, section in enumerate(page.get("sections") or []):
                if section.get("type") not in _IMAGE_SECTION_TYPES:
                    continue
                # Slot vacío si no hay asset_id y no hay image_url.
                if section.get("asset_id"):
                    continue
                if section.get("image_url"):
                    continue
                slots.append((page_idx, sec_idx, section["type"]))
        return slots

    @staticmethod
    def _resolve_budget(project: Project) -> Decimal:
        """Devuelve el budget del proyecto o el default 1.00 USD."""
        raw = project.image_generation_budget_usd
        if raw is None:
            return Decimal("1.00")
        return Decimal(str(raw))

    async def _process_slots(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        brief: dict[str, Any],
        client: OpenAIClient,
        empty_slots: list[tuple[int, int, str]],
        budget_usd: Decimal,
    ) -> dict[str, Any]:
        images_generated = 0
        images_failed = 0
        residuals_created = 0
        cost_total = Decimal("0")
        warnings: list[str] = []
        budget_exhausted = False

        business = brief.get("business") or {}
        brand = brief.get("brand") or {}

        for page_idx, sec_idx, section_type in empty_slots:
            if cost_total >= budget_usd:
                budget_exhausted = True
                remaining = len(empty_slots) - images_generated - images_failed
                if remaining > 0:
                    residuals_created += self._emit_residual_budget_exhausted(
                        ctx, project, remaining, cost_total, budget_usd,
                    )
                    warnings.append(
                        f"Budget agotado tras ${cost_total:.4f}. "
                        f"{remaining} slots no procesados."
                    )
                break

            quality, size = _TYPE_TO_IMAGE_PARAMS.get(
                section_type, ("medium", "1024x1024")
            )
            section = brief["pages"][page_idx]["sections"][sec_idx]
            prompt = self._build_prompt(business, brand, section, section_type)

            try:
                result = await client.generate_image(
                    prompt=prompt, quality=quality, size=size,
                )
                cost_total += Decimal(str(result.cost_usd))
                asset = self._persist_asset(
                    ctx=ctx, project=project,
                    result=result, alt_hint=section.get("headline") or section_type,
                )
                # Inyecta asset_id y metadata en la sección del Brief.
                section["asset_id"] = asset.id
                section["ai_image_metadata"] = {
                    "prompt": prompt,
                    "model": result.model,
                    "quality": quality,
                    "size": size,
                    "cost_usd": float(result.cost_usd),
                    "generated_at": datetime.now(UTC).isoformat(),
                }
                images_generated += 1
            except OpenAIClientError as e:
                images_failed += 1
                residuals_created += self._emit_residual_failed(
                    ctx, project, page_idx, sec_idx, section_type, e,
                )
                warnings.append(
                    f"Slot ({page_idx},{sec_idx}) tipo {section_type}: "
                    f"{str(e)[:80]}"
                )

        return {
            "slots_total": len(empty_slots),
            "images_generated": images_generated,
            "images_failed": images_failed,
            "residuals_created": residuals_created,
            "cost_total": float(cost_total),
            "budget_exhausted": budget_exhausted,
            "warnings": warnings,
        }

    @staticmethod
    def _build_prompt(
        business: dict[str, Any],
        brand: dict[str, Any],
        section: dict[str, Any],
        section_type: str,
    ) -> str:
        """Prompt determinista para gpt-image-2 brand-consistent."""
        biz_desc = business.get("description") or business.get("name") or "negocio"
        sector = business.get("sector") or "general"
        tone = business.get("tone_of_voice") or "friendly"
        colors_dict = brand.get("colors") or {}
        # Lista de hex/var legibles.
        primary = colors_dict.get("primary") or "neutral"
        secondary = colors_dict.get("secondary") or "neutral"

        intent_hint = {
            "hero": "imagen hero principal de alta calidad para banner web",
            "image": "imagen decorativa moderna para sección de contenido",
            "gallery": "imagen para galería de portfolio",
            "testimonial": "imagen abstracta para fondo de testimonios",
            "ai_generated": "imagen ilustrativa para sección de contenido",
        }.get(section_type, "imagen decorativa moderna")

        return (
            f"Genera {intent_hint} para un negocio del sector {sector}: "
            f"{biz_desc}. "
            f"Estilo visual: tono {tone}, paleta dominante "
            f"{primary} y {secondary}. "
            "Composición limpia, alta calidad fotográfica o ilustración "
            "moderna, sin texto sobreimpreso. Mobile-friendly."
        )

    @staticmethod
    def _persist_asset(
        *,
        ctx: AgentContext,
        project: Project,
        result: OpenAIImageResult,
        alt_hint: str,
    ) -> Asset:
        """Crea fila Asset con el PNG generado. En MVP guarda solo el
        hash (la subida real a R2 la hace AssetUploaderAgent en su
        siguiente pasada, igual que con assets scrapeados)."""
        sha = hashlib.sha256(result.image_bytes).hexdigest()
        # original_url placeholder: "ai-generated://<sha>".
        original_url = f"ai-generated://{sha}"
        asset = Asset(
            project_id=project.id,
            original_url=original_url,
            hash=sha,
            mime=result.mime,
            size_bytes=len(result.image_bytes),
            width=result.width,
            height=result.height,
            alt_text=alt_hint[:200] if alt_hint else None,
            status=AssetStatus.PENDING,
            sizes_json={
                "ai_generated": True,
                "model": result.model,
                "quality": result.quality,
                "size": result.size,
                "cost_usd": result.cost_usd,
            },
        )
        ctx.session.add(asset)
        ctx.session.flush()  # genera asset.id
        return asset

    def _emit_residual_failed(
        self,
        ctx: AgentContext,
        project: Project,
        page_idx: int,
        section_idx: int,
        section_type: str,
        error: Exception,
    ) -> int:
        task = ResidualTask(
            project_id=project.id,
            title=(
                f"Imagen IA falló — página {page_idx} sección {section_idx} "
                f"tipo {section_type}"
            ),
            description=(
                f"gpt-image-2 no pudo generar la imagen para esta sección. "
                f"Error: {str(error)[:300]}. "
                "Subir manualmente desde dashboard o reintentar."
            ),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=10,
            screenshot_paths=[],
            status=ResidualStatus.OPEN,
            generated_by="redesign_images",
        )
        ctx.session.add(task)
        return 1

    def _emit_residual_budget_exhausted(
        self,
        ctx: AgentContext,
        project: Project,
        remaining: int,
        cost_used: Decimal,
        budget: Decimal,
    ) -> int:
        task = ResidualTask(
            project_id=project.id,
            title=(
                f"Budget IA agotado — {remaining} imágenes sin generar"
            ),
            description=(
                f"El proyecto ha gastado ${cost_used:.4f} de ${budget:.2f} "
                "en imágenes IA. Quedan slots sin rellenar. "
                "Subir el budget del proyecto en /projects/[id]/preview o "
                "completar imágenes manualmente desde dashboard."
            ),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=15,
            screenshot_paths=[],
            status=ResidualStatus.OPEN,
            generated_by="redesign_images",
        )
        ctx.session.add(task)
        return 1
