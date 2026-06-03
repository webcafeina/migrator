"""BriefSectionAggregator — agrupa bloques planos en secciones semánticas (v0.29.0 B3).

Fix del bug raíz WCM-053: `BriefGenerator` emitía 1 `Brief.section` por cada
bloque HTML del extractor (text/heading/image/grid). Como `SectionPicker`
del pipeline Hybrid filtra por categoría del catálogo brickstemplate
(semantic: hero/features/cta/...), solo `hero` matcheaba — 0.6% de
secciones resueltas en E2E mariya.design.

Este agente se ejecuta entre `brief_generator` y `redesign_templates`, lee
`Project.brief_json.pages[i].sections[]` de bajo nivel, y los REEMPLAZA con
secciones semánticas canónicas (16 tipos verificados contra el catálogo).
Cada sección semántica:
- Tiene un `type` canónico (hero, features, cta, ...).
- Lista `source_blocks` con los bloques de bajo nivel absorbidos
  (para que RedesignTemplates extraiga slots).
- Marca `aggregated_at: ISO` por idempotencia entre re-runs.

Cache: cada página se SHA256-hash sobre sus bloques compactos. Si el
hash no cambia entre runs (origen no re-scrapeado), se reusa el agregado
y NO se llama al LLM. Esto reduce coste drásticamente en pipeline restart.

Coste estimado runtime: ~$0.30-0.80/proyecto (50 páginas × ~$0.01/llamada
gpt-5.5). Para proyectos con cache hit del 100%: $0.

Sin OPENAI_API_KEY → SKIPPED (warning). El pipeline sigue con el Brief
plano — RedesignTemplates emite residuals como en v0.28.0.

Idempotente: re-run sin cambios en blocks → no llama OpenAI, no toca
cost_usd, no cambia el Brief. Re-run tras re-scrape → invalida cache
para las páginas afectadas y re-agrega.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from wcm_bricks_transpiler.redesign.semantic_taxonomy import (
    CANONICAL_SECTION_TYPES,
    EXTRACTOR_NOISE_TYPES,
    SECTION_DESCRIPTIONS,
    canonical_for_extractor_type,
    is_canonical_type,
)
from wcm_db.models.projects import Project
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import (
    BriefAggregatorError,
    OpenAIClientError,
    OpenAIInvalidOutputError,
)
from wcm_worker.integrations.openai_client import OpenAIClient

log = logging.getLogger("wcm.worker.brief_aggregator")


#: Si una página tiene 0 o 1 bloque útil, no llamamos al LLM — usamos
#: el fast-path determinista (canonical_for_extractor_type) o saltamos.
_TRIVIAL_PAGE_THRESHOLD = 1


class BriefSectionAggregator(BaseAgent):
    name = "brief-aggregator"
    phase_name = "brief_aggregate"

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
    ) -> None:
        self._injected_client = openai_client

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise BriefAggregatorError("BriefSectionAggregator requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise BriefAggregatorError(f"Project {ctx.project_id} no existe")

        brief = project.brief_json
        if not brief or not brief.get("pages"):
            return AgentResult(
                summary=f"Project {project.id}: sin brief_json → SKIPPED",
                outputs={"skipped": True, "reason": "no_brief"},
            )

        client = self._injected_client or OpenAIClient.from_env()
        if client is None:
            log.warning(
                "brief_aggregator_no_openai",
                extra={"project_id": project.id},
            )
            return AgentResult(
                summary=(
                    f"Project {project.id}: sin OPENAI_API_KEY → SKIPPED "
                    "(pipeline sigue con Brief plano)"
                ),
                outputs={"skipped": True, "reason": "no_openai_key"},
                warnings=[
                    "Configurar OPENAI_API_KEY para activar el agregador semántico."
                ],
            )

        cache: dict[str, Any] = dict(project.brief_aggregation_cache_json or {})
        business_sector = (
            brief.get("business", {}).get("sector")
            or project.business_sector
        )

        n_pages_aggregated = 0
        n_pages_cache_hit = 0
        n_pages_fastpath = 0
        n_pages_skipped = 0
        cost_session = Decimal("0.0000")
        warnings: list[str] = []
        n_sections_before = sum(len(p.get("sections") or []) for p in brief["pages"])

        # Procesar cada página
        for page_idx, page in enumerate(brief["pages"]):
            sections = page.get("sections") or []
            # Filtrar ruido
            useful = [s for s in sections if s.get("type") not in EXTRACTOR_NOISE_TYPES]
            if len(useful) <= _TRIVIAL_PAGE_THRESHOLD:
                # Página trivial: aplicar fast-path por sección o dejar tal cual
                fastpath = self._try_fastpath(useful)
                if fastpath is not None:
                    page["sections"] = fastpath
                    page["aggregated_at"] = datetime.now(UTC).isoformat()
                    page["aggregation_method"] = "fastpath"
                    n_pages_fastpath += 1
                else:
                    n_pages_skipped += 1
                continue

            # Cache lookup
            page_sha = self._compute_blocks_sha(useful, page.get("intent"))
            cached = cache.get(page_sha)
            if cached:
                page["sections"] = copy.deepcopy(cached["sections"])
                page["aggregated_at"] = cached["generated_at"]
                page["aggregation_method"] = "cache"
                n_pages_cache_hit += 1
                continue

            # LLM call
            try:
                result = asyncio.run(
                    client.aggregate_page_sections(
                        page_url=page.get("slug") or page.get("title") or f"page_{page_idx}",
                        page_intent=page.get("intent"),
                        blocks=[
                            {"block_type": s.get("type"), "content_json": s}
                            for s in useful
                        ],
                        business_sector=business_sector,
                        canonical_taxonomy={t: SECTION_DESCRIPTIONS[t] for t in CANONICAL_SECTION_TYPES},
                    )
                )
            except (OpenAIInvalidOutputError, OpenAIClientError) as e:
                msg = (
                    f"Página '{page.get('slug')}': agregador LLM falló — "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                log.warning(
                    "brief_aggregator_llm_failed",
                    extra={
                        "project_id": project.id,
                        "page_slug": page.get("slug"),
                        "error": str(e)[:200],
                    },
                )
                warnings.append(msg)
                n_pages_skipped += 1
                continue

            llm_sections = (result.data or {}).get("sections") or []
            validated = self._validate_and_build_sections(
                llm_sections, source_blocks=useful, page_slug=page.get("slug") or "?",
            )
            if validated is None:
                msg = (
                    f"Página '{page.get('slug')}': output LLM inválido "
                    "(types fuera de taxonomía o source_block_ids inconsistentes)"
                )
                log.warning(
                    "brief_aggregator_invalid_output",
                    extra={
                        "project_id": project.id,
                        "page_slug": page.get("slug"),
                        "llm_section_types": [s.get("type") for s in llm_sections],
                    },
                )
                warnings.append(msg)
                n_pages_skipped += 1
                continue

            now_iso = datetime.now(UTC).isoformat()
            page["sections"] = validated
            page["aggregated_at"] = now_iso
            page["aggregation_method"] = "llm"

            cache[page_sha] = {
                "sections": validated,
                "model": result.model,
                "cost_usd": float(result.cost_usd),
                "generated_at": now_iso,
            }
            cost_session += Decimal(str(result.cost_usd))
            n_pages_aggregated += 1

        # Persistir
        project.brief_json = brief
        project.brief_aggregation_cache_json = cache
        existing_cost = Decimal(str(project.brief_aggregation_cost_usd or "0.0"))
        project.brief_aggregation_cost_usd = existing_cost + cost_session
        flag_modified(project, "brief_json")
        flag_modified(project, "brief_aggregation_cache_json")
        ctx.session.flush()

        n_sections_after = sum(len(p.get("sections") or []) for p in brief["pages"])
        ratio = (
            f"{n_sections_after}/{n_sections_before} "
            f"({n_sections_after * 100 // max(n_sections_before, 1)}%)"
        )

        return AgentResult(
            summary=(
                f"Project {project.id}: brief agregado · "
                f"{n_pages_aggregated} pages LLM · "
                f"{n_pages_cache_hit} cache · {n_pages_fastpath} fastpath · "
                f"{n_pages_skipped} skipped · "
                f"secciones {ratio} · coste sesión ${float(cost_session):.4f}"
            ),
            outputs={
                "skipped": False,
                "n_pages_aggregated_llm": n_pages_aggregated,
                "n_pages_cache_hit": n_pages_cache_hit,
                "n_pages_fastpath": n_pages_fastpath,
                "n_pages_skipped": n_pages_skipped,
                "n_sections_before": n_sections_before,
                "n_sections_after": n_sections_after,
                "cost_session_usd": float(cost_session),
                "cost_total_usd": float(project.brief_aggregation_cost_usd),
            },
            warnings=warnings,
        )

    # ---------- helpers ----------

    @staticmethod
    def _compute_blocks_sha(blocks: list[dict[str, Any]], intent: str | None) -> str:
        """SHA256 estable de la lista de bloques + intent. Cache key."""
        compact = [
            {
                "t": b.get("type"),
                # Solo keys que afectan al agregado semántico
                "h": b.get("headline") or "",
                "s": b.get("subheadline") or "",
                "x": (b.get("text") or b.get("html") or "")[:200],
                "a": b.get("alt") or "",
                "ct": b.get("cta_text") or "",
                "cu": b.get("cta_url") or "",
                "n": len(b.get("items") or []),
            }
            for b in blocks
        ]
        payload = json.dumps(
            {"intent": intent or "", "blocks": compact},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @staticmethod
    def _try_fastpath(
        blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        """Fast-path para páginas triviales (0-1 bloques): si el único
        bloque tiene un mapping directo, emite una sección semántica.
        Devuelve None si no procede (mantener tal cual)."""
        if not blocks:
            return []
        if len(blocks) == 1:
            t = blocks[0].get("type") or ""
            canonical = canonical_for_extractor_type(t)
            if canonical is not None:
                # Wrap el block en una sección canónica
                return [
                    {
                        "type": canonical,
                        "design_method": blocks[0].get("design_method") or "templates",
                        "source_blocks": [blocks[0]],
                        "headline": blocks[0].get("headline") or blocks[0].get("text") or "",
                        "has_image": bool(blocks[0].get("asset_id") or blocks[0].get("image_url")),
                        "has_cta": bool(blocks[0].get("cta_text")),
                    }
                ]
        return None

    @staticmethod
    def _validate_and_build_sections(
        llm_sections: list[dict[str, Any]],
        *,
        source_blocks: list[dict[str, Any]],
        page_slug: str,
    ) -> list[dict[str, Any]] | None:
        """Valida output del LLM y construye secciones finales con
        `source_blocks` resueltos desde source_block_ids.

        Devuelve None si la validación falla — el caller emite warning
        y la página queda sin agregar.
        """
        if not isinstance(llm_sections, list) or not llm_sections:
            return None

        n_blocks = len(source_blocks)
        seen_ids: set[int] = set()
        built: list[dict[str, Any]] = []

        for sec in llm_sections:
            if not isinstance(sec, dict):
                return None
            stype = sec.get("type")
            if not isinstance(stype, str) or not is_canonical_type(stype):
                return None
            ids = sec.get("source_block_ids") or []
            if not isinstance(ids, list) or not ids:
                return None
            resolved: list[dict[str, Any]] = []
            for bid in ids:
                if not isinstance(bid, int) or bid < 0 or bid >= n_blocks:
                    return None
                if bid in seen_ids:
                    return None
                seen_ids.add(bid)
                resolved.append(source_blocks[bid])

            # Heredar design_method del primer bloque absorbido (preserva
            # heurística por tipo del BriefGenerator) o "templates" default.
            design_method = (
                resolved[0].get("design_method") if resolved else None
            ) or "templates"

            built.append({
                "type": stype,
                "design_method": design_method,
                "source_blocks": resolved,
                "headline": sec.get("headline") or "",
                "subheadline": sec.get("subheadline") or "",
                "summary": sec.get("summary") or "",
                "has_image": bool(sec.get("has_image")),
                "has_cta": bool(sec.get("has_cta")),
            })

        # Cobertura total
        if seen_ids != set(range(n_blocks)):
            return None
        return built


__all__ = ["BriefSectionAggregator"]
