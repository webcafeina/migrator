"""LLMSectionRanker — elige el mejor template entre N candidatos vía LLM.

v0.28.0 B14. Mejora la calidad estética del pipeline Templates/Hybrid
sustituyendo la selección por hash determinista de `SectionPicker` por
una elección semántica del LLM (gpt-5.5 default).

Diseño:
- Función pura `choose()` con I/O inyectado (callable LLM + callable cache).
- Sin dependencia directa de SQLAlchemy ni OpenAI SDK — solo dicts y
  callables. Testeable sin mocks complejos.
- Cache por `(section_index, candidates_hash)` → idempotente entre runs.
- Fallback al hash si LLM falla o devuelve ID inexistente.

Coste estimado: ~$0.01 por sección (gpt-5.5 ~1.5K tokens). Proyecto
50 páginas × 6 secciones AI ≈ $3 extra.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("wcm.bricks_transpiler.redesign.llm_ranker")

#: Coste estimado por sección (para budget tracking del agente).
DEFAULT_COST_PER_CHOICE_USD = 0.012

#: Máximo de candidatos enviados al LLM. Si hay más, se hace sample
#: random determinista por section_index para mantener prompt manejable.
MAX_CANDIDATES_SENT_TO_LLM = 30


@dataclass(frozen=True)
class RankResult:
    """Resultado de `LLMSectionRanker.choose()`."""

    template_id: str
    rationale: str
    cache_hit: bool
    cost_usd: float  # 0.0 si cache_hit
    fallback_used: bool  # True si LLM falló y caímos al hash


def candidates_hash(candidates: list[dict[str, Any]]) -> str:
    """SHA256 corto del set de IDs de candidatos. Sirve como cache key."""
    ids = sorted(c.get("id", "") for c in candidates)
    payload = json.dumps(ids, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def cache_key(section_index: int, candidates: list[dict[str, Any]]) -> str:
    """Cache key estable: `{section_index}:{candidates_sha[:8]}`."""
    return f"{section_index}:{candidates_hash(candidates)}"


class LLMSectionRanker:
    """Motor de selección semántica de templates con cache + fallback.

    `llm_call`: callable async `(brief_context, section_spec, candidates_subset)
    → {template_id, rationale, cost_usd}`. Devuelve None si el LLM falla
    (se delega el fallback al ranker).

    `hash_fallback`: callable síncrono `(business_name, candidates) → str`
    que devuelve un template_id válido (típicamente la lógica actual de
    `SectionPicker._try_match` con hash determinista).
    """

    def __init__(
        self,
        *,
        llm_call: Callable[[dict, dict, list], Awaitable[dict | None]],
        hash_fallback: Callable[[str, list], str],
    ) -> None:
        self._llm_call = llm_call
        self._hash_fallback = hash_fallback

    async def choose(
        self,
        *,
        section_index: int,
        section_spec: dict[str, Any],
        candidates: list[dict[str, Any]],
        brief_context: dict[str, Any],
        cache: dict[str, dict[str, Any]] | None = None,
    ) -> RankResult:
        """Devuelve el template elegido. Mutación in-place del `cache` si
        hay miss y se persiste la elección — el caller debe persistir el
        cache mutado a BD después.

        Optimizaciones:
        - N=0 → no se llama LLM (el caller debe haber detectado esto antes).
        - N=1 → atajo: devuelve el único candidato sin llamar LLM.
        - cache hit por (section_index, candidates_sha) → reusa elección.
        - N>MAX → sample sub-set determinista por section_index.
        """
        if not candidates:
            raise ValueError("LLMSectionRanker.choose() exige N>=1 candidatos")

        # Atajo N=1
        if len(candidates) == 1:
            chosen_id = candidates[0].get("id", "")
            return RankResult(
                template_id=chosen_id,
                rationale="single candidate",
                cache_hit=False,
                cost_usd=0.0,
                fallback_used=False,
            )

        # Cache lookup
        ck = cache_key(section_index, candidates)
        if cache is not None and ck in cache:
            entry = cache[ck]
            return RankResult(
                template_id=entry["template_id"],
                rationale=entry.get("rationale", ""),
                cache_hit=True,
                cost_usd=0.0,
                fallback_used=False,
            )

        # Sub-set determinista si N>MAX
        subset = _subset_for_llm(candidates, section_index, MAX_CANDIDATES_SENT_TO_LLM)

        # Llamar LLM
        valid_ids = {c.get("id") for c in subset}
        try:
            llm_result = await self._llm_call(brief_context, section_spec, subset)
        except Exception as e:  # noqa: BLE001 — defensivo, fallback al hash
            log.warning(
                "llm_ranker_call_failed err=%s — fallback al hash",
                str(e)[:200],
            )
            llm_result = None

        chosen_id: str | None = None
        rationale = ""
        cost = 0.0
        if isinstance(llm_result, dict):
            candidate_id = llm_result.get("template_id")
            if isinstance(candidate_id, str) and candidate_id in valid_ids:
                chosen_id = candidate_id
                rationale = llm_result.get("rationale", "") or ""
                cost = float(llm_result.get("cost_usd") or DEFAULT_COST_PER_CHOICE_USD)
            else:
                log.warning(
                    "llm_ranker_invalid_id_returned id=%s — fallback al hash",
                    candidate_id,
                )

        fallback_used = chosen_id is None
        if chosen_id is None:
            # Fallback determinista: usar la lógica actual del SectionPicker.
            business_name = (brief_context.get("business") or {}).get("name") or ""
            chosen_id = self._hash_fallback(business_name, candidates)
            rationale = "fallback: hash determinista (LLM falló o devolvió ID inválido)"

        # Persistir en cache
        if cache is not None and not fallback_used:
            cache[ck] = {
                "template_id": chosen_id,
                "rationale": rationale,
                "cost_usd": cost,
            }

        return RankResult(
            template_id=chosen_id,
            rationale=rationale,
            cache_hit=False,
            cost_usd=cost,
            fallback_used=fallback_used,
        )


def _subset_for_llm(
    candidates: list[dict[str, Any]],
    section_index: int,
    max_n: int,
) -> list[dict[str, Any]]:
    """Si N>max_n, devuelve una sub-muestra determinista por `section_index`.
    Mismo (candidates, section_index) → mismo subset entre re-runs."""
    if len(candidates) <= max_n:
        return candidates
    # Rotación determinista: empezar desde un offset basado en hash(section_index).
    h = int(hashlib.md5(str(section_index).encode()).hexdigest()[:8], 16)
    start = h % len(candidates)
    rotated = candidates[start:] + candidates[:start]
    return rotated[:max_n]


__all__ = ["LLMSectionRanker", "RankResult", "cache_key", "candidates_hash"]
