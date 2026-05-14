"""Fingerprinter — identifica el constructor/CMS de una URL.

Cascada de detección (5 niveles, coste creciente):
  1. Headers HTTP                — HEAD request, barato
  2. HTML markers (regex, meta)  — GET + parse
  3. Recursos cargados (CDN dom) — GET + scan
  4. JS globals (`window.*`)     — requiere Playwright (lsr-fingerprint)
  5. DOM patterns                 — requiere Playwright

Niveles 1-3 viven aquí (sin browser). Niveles 4-5 viven en `lsr.py`
(opcional, importa Playwright).

Patterns canónicos en `.claude/skills/builtwith-fingerprint/patterns.yml`.
Confidence acumulativa por tech (max 1.0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Resolución del patterns.yml siguiendo el repo desde el módulo instalado.
# Cadena: fingerprint.py → wcm_scraper_core/ → src/ → scraper-core/ → packages/ → REPO_ROOT
# parents[4] = REPO_ROOT (con install editable). Si se instalara como wheel real,
# el path no estaría disponible y haría falta empaquetar patterns.yml como data
# del paquete; pendiente para Fase 15 si se distribuye fuera del monorepo.
_PATTERNS_PATH = (
    Path(__file__).resolve().parents[4]
    / ".claude"
    / "skills"
    / "builtwith-fingerprint"
    / "patterns.yml"
)


@dataclass
class TechMatch:
    name: str
    category: str
    confidence: float  # 0.0 - 1.0
    evidence: list[str] = field(default_factory=list)


@dataclass
class FingerprintResult:
    matches: list[TechMatch]
    raw_signals_count: int

    def best_builder(self) -> TechMatch | None:
        """Devuelve la "plataforma base" del sitio para fines de clasificación.

        Orden de prioridad: **cms > ecommerce > builder**. Cuando coexisten
        un CMS (WordPress) y un builder dependiente (Elementor, Divi,
        Bricks), gana el CMS — la plataforma base es lo que importa para
        migración, no el builder visual encima. Mismo principio con
        Shopify (ecommerce) sobre cualquier builder visual del tema.

        Antes solo consideraba `category=builder`, lo cual hacía que sitios
        WordPress+Elementor se clasificaran como "Elementor" (no presente
        en `BuilderType` → caía a OTHER), perdiendo la información útil.
        """
        for category in ("cms", "ecommerce", "builder"):
            matches = [m for m in self.matches if m.category == category]
            if matches:
                return max(matches, key=lambda m: m.confidence)
        return None

    def by_category(self, category: str) -> list[TechMatch]:
        return [m for m in self.matches if m.category == category]


@lru_cache(maxsize=1)
def _load_patterns(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _PATTERNS_PATH
    if not p.exists():  # pragma: no cover
        raise FileNotFoundError(
            f"patterns.yml no encontrado en {p}. Verifica la estructura del repo."
        )
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _match_html(html: str, signal: dict[str, Any]) -> bool:
    pattern = signal["regex"]
    return bool(re.search(pattern, html))


def _match_header(headers: dict[str, str], signal: dict[str, Any]) -> bool:
    key = signal["key"].lower()
    headers_lower = {k.lower(): v for k, v in headers.items()}
    if key not in headers_lower:
        return False
    if "value" in signal:
        return bool(re.search(signal["value"], headers_lower[key]))
    return True


def _match_meta(html: str, signal: dict[str, Any]) -> bool:
    name = signal["name"]
    pattern = signal["value"]
    meta_re = rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']'
    m = re.search(meta_re, html, re.IGNORECASE)
    if not m:
        return False
    return bool(re.search(pattern, m.group(1)))


def fingerprint_url(
    *,
    html: str,
    headers: dict[str, str] | None = None,
    js_globals: dict[str, bool] | None = None,
    min_confidence: float = 0.3,
    patterns_path: str | None = None,
) -> FingerprintResult:
    """Aplica los patterns sobre la respuesta capturada.

    `js_globals` se pasa solo si se ha renderizado con Playwright (lsr).
    Si es None, los signals de tipo `js_global` se ignoran silenciosamente.
    """
    patterns = _load_patterns(patterns_path)
    headers = headers or {}
    js_globals = js_globals or {}

    matches: list[TechMatch] = []
    raw_signals = 0

    for tech in patterns.get("technologies", []):
        confidence = 0.0
        evidence: list[str] = []
        for signal in tech.get("signals", []):
            stype = signal["type"]
            try:
                hit = False
                if stype == "header":
                    hit = _match_header(headers, signal)
                elif stype == "html":
                    hit = _match_html(html, signal)
                elif stype == "meta":
                    hit = _match_meta(html, signal)
                elif stype == "js_global":
                    hit = bool(js_globals.get(signal["key"]))
                elif stype == "cookie":
                    # Cookies pueden venir como header 'set-cookie' o
                    # 'cookie' en request; conservador: regex en headers.
                    cookie_hdr = headers.get("set-cookie", "")
                    hit = signal["key"] in cookie_hdr
            except (re.error, KeyError):
                hit = False
            if hit:
                raw_signals += 1
                evidence.append(f"{stype}:{signal.get('key', signal.get('regex', signal.get('name', '?')))}")
                confidence += float(signal["weight"])
        if confidence >= min_confidence:
            matches.append(
                TechMatch(
                    name=tech["name"],
                    category=tech["category"],
                    confidence=min(confidence, 1.0),
                    evidence=evidence,
                )
            )

    matches.sort(key=lambda m: m.confidence, reverse=True)
    return FingerprintResult(matches=matches, raw_signals_count=raw_signals)
