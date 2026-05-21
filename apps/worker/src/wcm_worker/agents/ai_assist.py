"""AiAssistAgent — re-procesa bloques pobres con Claude Vision (AI.4).

Fase nueva del pipeline v0.22.0 entre `theme_styles` y `transpile_bricks`.

Flujo por proyecto:
1. Cargar `content_blocks` candidatos: `block_type=UNKNOWN` o
   `coverage_score < 0.6` y `ai_processed=False`.
2. Por cada bloque (en lotes de 5 paralelos):
   a. Descargar el screenshot R2 (`section_screenshot_url`).
   b. Construir HTML stub de la sección (desde `page.html_clean` + selector).
   c. Invocar `ClaudeVisionClient.transpile_section()`.
   d. Si Claude devuelve elementos válidos → `block_type=AI_GENERATED`,
      `content_json.bricks_elements = [...]`.
   e. Si Claude falla (5xx, auth, invalid output) → `block_type=RAW_HTML`,
      `content_json = {html, css}` con el HTML del origen (sección).
3. Marcar `ai_processed=True` en todos los bloques procesados
   (idempotencia entre runs).
4. Budget cap via `WCM_AI_BUDGET_USD_PER_PROJECT` (default $10): si se
   alcanza, abortar el resto del batch + ResidualTask con el coste.

Sin `ANTHROPIC_API_KEY` configurada → el agente marca todos los
candidatos como RAW_HTML (sin tocar API). El operador puede setear la
key y re-ejecutar para mejorar calidad.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from sqlalchemy import select

from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import (
    BlockType,
    ResidualCategory,
    ResidualStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import AiAssistError
from wcm_worker.integrations.claude_vision import (
    ClaudeVisionApiError,
    ClaudeVisionAuthError,
    ClaudeVisionClient,
    ClaudeVisionInvalidOutputError,
    make_client_from_env,
)

log = logging.getLogger("wcm.worker.ai_assist")

#: Umbral de coverage_score por defecto: bloques bajo este valor se
#: consideran candidatos a AI. Override por env
#: `WCM_AI_COVERAGE_THRESHOLD`.
DEFAULT_COVERAGE_THRESHOLD = 0.6

#: Concurrency: cuántas secciones procesamos en paralelo. Anthropic
#: rate-limit es generoso pero no infinito; 5 balancea velocidad con
#: respeto al rate-limit del free/standard tier.
#: v0.23.0 — Reducido de 5 → 2 para respetar rate-limit Anthropic en
#: tiers bajos (~5 req/min). El bloque F del sprint v0.23.0 demostró
#: que concurrency=5 con tier bajo saturaba el cliente y caía masivo a
#: RAW. Con 2 + retries=5 + pausa 60s en 429 el ratio AI:RAW mejora.
DEFAULT_CONCURRENCY = 2

#: Presupuesto USD por proyecto. Si el coste acumulado lo supera,
#: aborta resto + emite ResidualTask. Override por env
#: `WCM_AI_BUDGET_USD_PER_PROJECT`.
DEFAULT_BUDGET_USD = 10.0

#: Cap absoluto de bloques procesados por proyecto. Importante con tiers
#: gratuitos/básicos de Anthropic (5-50 req/min) que asfixian retries
#: exponenciales. Por defecto 30 — cubre las secciones clave (hero, nav,
#: footer, grids principales) y deja el resto como RAW_HTML. Override
#: por env `WCM_AI_MAX_BLOCKS_PER_PROJECT`. Set a 0 para sin límite.
DEFAULT_MAX_BLOCKS = 30


class AiAssistAgent(BaseAgent):
    name = "ai-assist"
    phase_name = "ai_assist"

    def __init__(
        self,
        *,
        client: ClaudeVisionClient | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._injected_client = client
        self._injected_http = http_client

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise AiAssistError("AiAssistAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise AiAssistError(f"Project {ctx.project_id} no encontrado")

        candidates = self._load_candidates(ctx, ctx.project_id)

        # Cap absoluto — protege del rate-limit Anthropic en tiers bajos.
        max_blocks = self._resolve_max_blocks()
        deferred_count = 0
        if max_blocks > 0 and len(candidates) > max_blocks:
            deferred_blocks = candidates[max_blocks:]
            candidates = candidates[:max_blocks]
            deferred_count = len(deferred_blocks)
            # Los diferidos se marcan como RAW_HTML directamente
            # (`ai_processed=True` para no reintentarlos en Resume).
            for b in deferred_blocks:
                self._apply_raw_html(ctx, b, reason="deferred_by_cap")
            log.info(
                "ai_assist_max_blocks_cap",
                extra={
                    "project_id": ctx.project_id,
                    "max_blocks": max_blocks,
                    "deferred": deferred_count,
                },
            )

        if not candidates:
            return AgentResult(
                summary=f"Project {project.id}: 0 bloques candidatos a AI assist",
                outputs={
                    "candidates": 0,
                    "ai_generated": 0,
                    "raw_html": 0,
                    "skipped": True,
                    "reason": "no_candidates",
                },
            )

        client = self._injected_client or make_client_from_env()
        if client is None:
            # Sin API key → todos a RAW_HTML.
            count = self._mark_all_as_raw(ctx, candidates)
            return AgentResult(
                summary=(
                    f"Project {project.id}: ANTHROPIC_API_KEY no configurada — "
                    f"{count} bloques marcados como RAW_HTML"
                ),
                outputs={
                    "candidates": len(candidates),
                    "ai_generated": 0,
                    "raw_html": count,
                    "skipped_api": True,
                },
                warnings=[
                    "ANTHROPIC_API_KEY no configurada. ai_assist hace "
                    "fallback a RAW_HTML para todos los bloques candidatos. "
                    "Configurar la key y re-ejecutar la fase para mejorar "
                    "fidelidad visual."
                ],
            )

        budget_usd = self._resolve_budget()
        concurrency = self._resolve_concurrency()

        stats = asyncio.run(
            self._process_all(
                ctx=ctx,
                project=project,
                client=client,
                candidates=candidates,
                budget_usd=budget_usd,
                concurrency=concurrency,
            )
        )

        # Persistir cambios.
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: {stats['ai_generated']} AI_GENERATED, "
                f"{stats['raw_html']} RAW_HTML, ${stats['cost_usd']:.2f} coste "
                f"({stats['cache_hits']} cache hits)"
            ),
            outputs=stats,
        )

    # ---------- helpers ----------

    def _load_candidates(
        self, ctx: AgentContext, project_id: int
    ) -> list[ContentBlock]:
        """Bloques candidatos: UNKNOWN o coverage_score<threshold, sin procesar."""
        threshold = self._resolve_threshold()
        stmt = (
            select(ContentBlock)
            .where(
                ContentBlock.project_id == project_id,
                ContentBlock.ai_processed.is_(False),
            )
            .order_by(ContentBlock.id.asc())
        )
        all_blocks = list(ctx.session.execute(stmt).scalars())
        return [
            b
            for b in all_blocks
            if b.block_type == BlockType.UNKNOWN
            or (b.coverage_score is not None and b.coverage_score < threshold)
        ]

    def _resolve_threshold(self) -> float:
        env = os.environ.get("WCM_AI_COVERAGE_THRESHOLD")
        if env:
            try:
                return float(env)
            except ValueError:
                log.warning(
                    "ai_assist_invalid_threshold",
                    extra={"value": env},
                )
        return DEFAULT_COVERAGE_THRESHOLD

    def _resolve_budget(self) -> float:
        env = os.environ.get("WCM_AI_BUDGET_USD_PER_PROJECT")
        if env:
            try:
                return float(env)
            except ValueError:
                log.warning("ai_assist_invalid_budget", extra={"value": env})
        return DEFAULT_BUDGET_USD

    def _resolve_concurrency(self) -> int:
        env = os.environ.get("WCM_AI_CONCURRENCY")
        if env:
            try:
                v = int(env)
                if 1 <= v <= 20:
                    return v
            except ValueError:
                pass
        return DEFAULT_CONCURRENCY

    def _resolve_max_blocks(self) -> int:
        env = os.environ.get("WCM_AI_MAX_BLOCKS_PER_PROJECT")
        if env:
            try:
                v = int(env)
                if v >= 0:
                    return v
            except ValueError:
                log.warning("ai_assist_invalid_max_blocks", extra={"value": env})
        return DEFAULT_MAX_BLOCKS

    def _mark_all_as_raw(
        self, ctx: AgentContext, candidates: list[ContentBlock]
    ) -> int:
        count = 0
        for block in candidates:
            self._apply_raw_html(ctx, block, reason="no_api_key")
            count += 1
        ctx.session.flush()
        return count

    def _apply_raw_html(
        self,
        ctx: AgentContext,
        block: ContentBlock,
        *,
        reason: str = "ai_failed",
    ) -> None:
        """v0.23.0 — alias de compatibilidad. NO emite nuevos RAW_HTML.

        Delega en `_apply_unresolved` que marca el bloque UNKNOWN +
        crea ResidualTask con captura para que el operador lo rehaga
        manualmente. Mantenemos la firma para tests/callers existentes.
        """
        self._apply_unresolved(ctx, block, reason=reason)

    def _apply_unresolved(
        self,
        ctx: AgentContext,
        block: ContentBlock,
        *,
        reason: str = "ai_failed",
    ) -> None:
        """v0.23.0 — Marca un bloque como UNKNOWN y crea una ResidualTask
        con captura para que el operador lo rehaga manualmente desde el
        editor Bricks.

        Reemplaza al antiguo `_apply_raw_html` que inyectaba HTML+CSS
        del origen como elemento `code` Bricks. Ese approach tumbaba el
        servidor cPanel cuando un proyecto tenía 100+ RAW (cada uno con
        ~262KB de CSS namespaceado en postmeta = >25MB por página).

        Pipeline:
        - `block.block_type = UNKNOWN` + `ai_processed = True` para que
          `bricks_transpiler` lo salte (no emite element).
        - `content_json` conserva `raw_html` y añade `_unresolved_reason`,
          `_source_selector`, `_screenshot_url` para diagnóstico.
        - Crea `ResidualTask(category=VISUAL_CONTENT, ...)` con el
          screenshot adjunto. Detalle en `checklist_generator` que
          agrupa estos residuales bajo "Bloques pendientes manual".
        """
        existing_json = block.content_json or {}
        raw_html = (
            existing_json.get("raw_html")
            or existing_json.get("html")
            or ""
        )
        screenshot_url = block.section_screenshot_url
        block.content_json = {
            "raw_html": raw_html[:5000],  # cap para no inflar BD
            "_unresolved_reason": reason,
            "_screenshot_url": screenshot_url,
        }
        block.block_type = BlockType.UNKNOWN
        block.ai_processed = True
        ctx.session.add(block)

        # Crear residual con captura. Asignamos category=VISUAL_CONTENT
        # porque es lo que mejor encaja en el enum existente: bloque
        # visual sin auto-resolución.
        task = ResidualTask(
            project_id=block.project_id,
            title=f"Bloque visual pendiente de rehacer manualmente — {block.id}",
            description=(
                f"El bloque #{block.id} (page {block.page_id}) no pudo "
                "resolverse automáticamente (ni por heurística enriquecida "
                f"ni por Claude Vision). Razón: {reason}. "
                "Abrir el editor Bricks y reconstruir la sección "
                "siguiendo la captura del origen adjunta."
            ),
            category=ResidualCategory.VISUAL_CONTENT,
            estimated_minutes=10,
            screenshot_paths=[],
            section_screenshot_url=screenshot_url,
            status=ResidualStatus.OPEN,
            generated_by="ai_assist",
        )
        ctx.session.add(task)

    def _load_page_css(self, ctx: AgentContext, page_id: int | None) -> str:
        """Devuelve `scraped_pages.css_extracted` o "" si no disponible.

        v0.23.0: mantenido por compat. Los nuevos `_apply_unresolved`
        ya no inyectan CSS (RAW eliminado).
        """
        if page_id is None:
            return ""
        page = ctx.session.get(ScrapedPage, page_id)
        if page is None:
            return ""
        return page.css_extracted or ""

    def _apply_ai_generated(
        self,
        ctx: AgentContext,
        block: ContentBlock,
        elements: list[dict[str, Any]],
        notes: str,
    ) -> None:
        block.content_json = {
            "bricks_elements": elements,
            "notes": notes,
        }
        block.block_type = BlockType.AI_GENERATED
        block.ai_processed = True
        ctx.session.add(block)

    async def _process_all(
        self,
        *,
        ctx: AgentContext,
        project: Project,
        client: ClaudeVisionClient,
        candidates: list[ContentBlock],
        budget_usd: float,
        concurrency: int,
    ) -> dict[str, Any]:
        # Pre-cargar todos los scraped_pages para los candidatos.
        page_ids = {b.page_id for b in candidates}
        pages_by_id: dict[int, ScrapedPage] = {}
        if page_ids:
            stmt = select(ScrapedPage).where(ScrapedPage.id.in_(page_ids))
            for sp in ctx.session.execute(stmt).scalars():
                pages_by_id[sp.id] = sp

        sem = asyncio.Semaphore(concurrency)
        http = self._injected_http or httpx.AsyncClient(timeout=30.0)
        owns_http = self._injected_http is None

        total_cost = 0.0
        ai_generated = 0
        raw_html_count = 0
        cache_hits = 0
        aborted_budget = False

        async def _one(block: ContentBlock) -> tuple[str, float, bool]:
            """Devuelve (outcome, cost, cache_hit) por bloque."""
            nonlocal total_cost
            async with sem:
                # Si el budget ya se alcanzó, fallback a RAW sin llamar API.
                if total_cost >= budget_usd:
                    return ("raw_html_budget", 0.0, False)

                screenshot_url = block.section_screenshot_url
                if not screenshot_url:
                    return ("raw_html_no_screenshot", 0.0, False)

                # Descargar el PNG.
                try:
                    resp = await http.get(screenshot_url)
                    if resp.status_code != 200:
                        log.warning(
                            "ai_assist_screenshot_404",
                            extra={
                                "block_id": block.id,
                                "url": screenshot_url,
                                "status": resp.status_code,
                            },
                        )
                        return ("raw_html_no_screenshot", 0.0, False)
                    screenshot_bytes = resp.content
                except httpx.RequestError as e:
                    log.warning(
                        "ai_assist_screenshot_fetch_failed",
                        extra={"block_id": block.id, "error": str(e)[:200]},
                    )
                    return ("raw_html_no_screenshot", 0.0, False)

                # HTML de la sección — usamos raw_html del content_json
                # si está; sino fragmento del html_clean.
                content_json = block.content_json or {}
                html_section = (
                    content_json.get("raw_html")
                    or content_json.get("html")
                    or ""
                )
                page = pages_by_id.get(block.page_id)
                selector = f"#section-{block.id}"  # placeholder identificador
                if page and not html_section:
                    # Fragmento conservador: primer 8KB del html_clean.
                    html_section = (page.html_clean or "")[:8000]

                try:
                    result = await client.transpile_section(
                        screenshot_png=screenshot_bytes,
                        html=html_section,
                        selector=selector,
                        project_id=project.id,
                        session=ctx.session,
                    )
                except ClaudeVisionAuthError as e:
                    # 401 — señal especial; el caller para todo el
                    # batch y marca el resto como RAW (auth_failed).
                    log.error(
                        "ai_assist_claude_auth_failed",
                        extra={
                            "block_id": block.id,
                            "error": str(e)[:200],
                        },
                    )
                    return ("auth_failed", 0.0, False)
                except (ClaudeVisionApiError, ClaudeVisionInvalidOutputError) as e:
                    log.warning(
                        "ai_assist_claude_failed",
                        extra={
                            "block_id": block.id,
                            "error": f"{type(e).__name__}: {str(e)[:200]}",
                        },
                    )
                    return ("raw_html_ai_failed", 0.0, False)

                total_cost += result.cost_usd
                return ("ai_generated", result.cost_usd, result.cache_hit), \
                    result.elements, result.notes  # type: ignore[return-value]

        # Ejecutar en paralelo respetando semáforo.
        tasks = [asyncio.create_task(_one(b)) for b in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados. Si CUALQUIER bloque devuelve "auth_failed",
        # marca todos los demás también como RAW (sin importar lo que
        # hicieron). En la práctica como las tareas corren en paralelo
        # con semáforo de N, las primeras N detectarán el auth fail antes
        # de que las demás lleguen al SDK; las que ya devolvieron
        # ai_generated se conservan.
        auth_failed_seen = False
        outcomes: list[tuple[Any, Any]] = []  # [(block, res)]
        for block, res in zip(candidates, results, strict=True):
            if isinstance(res, tuple) and len(res) == 3 and res[0] == "auth_failed":
                auth_failed_seen = True
            outcomes.append((block, res))

        for block, res in outcomes:
            if isinstance(res, Exception):
                log.warning(
                    "ai_assist_task_exception",
                    extra={"block_id": block.id, "error": str(res)[:200]},
                )
                self._apply_raw_html(ctx, block, reason="task_exception")
                raw_html_count += 1
                continue
            # res es tupla flexible:
            #   - ("raw_html_*", cost, cache_hit) → fallback RAW
            #   - ("auth_failed", cost, cache_hit) → fallback RAW (auth_failed)
            #   - (("ai_generated", cost, cache_hit), elements, notes)
            if isinstance(res, tuple) and len(res) == 3 and isinstance(res[0], str):
                outcome, _cost, _ch = res
                self._apply_raw_html(ctx, block, reason=outcome)
                raw_html_count += 1
                continue
            if isinstance(res, tuple) and len(res) == 3 and isinstance(res[0], tuple):
                (outcome, cost, cache_hit), elements, notes = res
                self._apply_ai_generated(ctx, block, elements, notes)
                ai_generated += 1
                if cache_hit:
                    cache_hits += 1

        if total_cost >= budget_usd:
            aborted_budget = True
            ctx.session.add(
                self._budget_residual(project, total_cost, budget_usd)
            )

        if owns_http:
            await http.aclose()

        return {
            "candidates": len(candidates),
            "ai_generated": ai_generated,
            "raw_html": raw_html_count,
            "cost_usd": round(total_cost, 4),
            "cache_hits": cache_hits,
            "aborted_budget": aborted_budget,
            "aborted_auth": auth_failed_seen,
            "budget_usd": budget_usd,
        }

    def _budget_residual(
        self, project: Project, cost_usd: float, budget_usd: float
    ) -> ResidualTask:
        return ResidualTask(
            project_id=project.id,
            title=(
                f"ai_assist alcanzó el budget de ${budget_usd:.2f} "
                f"(coste actual: ${cost_usd:.2f})"
            ),
            description=(
                f"La fase ai_assist procesó bloques hasta alcanzar el "
                f"presupuesto USD configurado. Los bloques restantes "
                f"fueron marcados como RAW_HTML (fallback).\n\n"
                f"Para procesar más bloques con AI:\n"
                f"1. Sube `WCM_AI_BUDGET_USD_PER_PROJECT` en `.env`.\n"
                f"2. Reanuda la fase ai_assist con "
                f"`POST /projects/{project.id}/resume?force_phase=ai_assist`."
            ),
            category=ResidualCategory.POST_GO_LIVE,
            estimated_minutes=10,
            screenshot_paths=[],
            generated_by="ai-assist",
            status=ResidualStatus.OPEN,
        )
