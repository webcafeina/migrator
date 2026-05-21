"""ThemeStylesAgent — sintetiza Theme Styles desde computed styles del origen.

C.3 (2026-05-21). Corre entre `extract_content` y `transpile_bricks`.

Input:
- `scraped_pages.dom_tree_json` de la home (primera página por
  depth/id), capturado por scraper_origin (C.2) vía Playwright
  getComputedStyle de selectores clave.

Output:
- `projects.theme_styles_origin` (JSONB):
    {
      "colors":     {"primary": "#000", "bg": "#fff", "text": "#000", "accent": "#b1f100"},
      "typography": {"h1": {...}, "h2": {...}, "body": {...}, "button": {...}},
      "spacing":    {"section_y": "80px", "container_y": "24px"}
    }

Heurística de síntesis (deliberadamente simple para MVP):
- `colors.bg`     = body.background-color (si transparente → #ffffff)
- `colors.text`   = body.color
- `colors.primary`= button.background-color o .wixui-button
- `colors.accent` = a.color
- `typography.*`  = los DEFAULT_STYLE_PROPS evaluados de cada selector
- `spacing`       = defaults razonables (Wix no expone esto en computed
  del body; el operador ajusta en Bricks tras Publish)

Resiliencia (ThemeStylesError.blocks_pipeline=False):
- Sin scraped_pages → SKIPPED con summary, sin theme_styles_origin.
- Sin dom_tree_json en la home → SKIPPED ídem.
- Colores no parseables → defaults safe (#ffffff, #000000).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ThemeStylesError

log = logging.getLogger("wcm.worker.theme_styles")

#: Defaults usados si la heurística no puede sintetizar un valor.
DEFAULT_BG = "#ffffff"
DEFAULT_TEXT = "#000000"
DEFAULT_PRIMARY = "#000000"
DEFAULT_ACCENT = "#b1f100"  # Lima de marca Webcafeína como fallback.

DEFAULT_SECTION_PADDING_Y = "80px"
DEFAULT_CONTAINER_PADDING_Y = "24px"

#: regex para extraer componentes de un valor CSS color rgb/rgba.
_RE_RGB = re.compile(
    r"rgba?\s*\(\s*"
    r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
    r"(?:\s*,\s*([\d.]+))?\s*\)"
)


class ThemeStylesAgent(BaseAgent):
    name = "theme-styles"
    phase_name = "theme_styles"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise ThemeStylesError("ThemeStylesAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise ThemeStylesError(f"Project {ctx.project_id} no encontrado")

        # Primera página por depth/id → la home en BFS.
        home = ctx.session.execute(
            select(ScrapedPage)
            .where(
                ScrapedPage.project_id == project.id,
                ScrapedPage.status == ScrapeStatus.SUCCESS,
            )
            .order_by(ScrapedPage.depth.asc(), ScrapedPage.id.asc())
            .limit(1)
        ).scalar_one_or_none()

        if home is None:
            return AgentResult(
                summary=f"Project {project.id}: sin scraped_pages, theme SKIPPED",
                outputs={"skipped": True, "reason": "no_scraped_pages"},
            )

        computed = home.dom_tree_json or {}
        if not isinstance(computed, dict) or not computed:
            return AgentResult(
                summary=(
                    f"Project {project.id}: home sin dom_tree_json "
                    "(scraper sin Playwright o capture_styles=False) — theme SKIPPED"
                ),
                outputs={"skipped": True, "reason": "no_computed_styles"},
                warnings=["dom_tree_json vacío — no se puede sintetizar theme"],
            )

        theme = synthesize_theme(computed)
        project.theme_styles_origin = theme

        # Persistencia explicita (defensive: por si la session config no
        # autoflushea el mutación in-place del JSONB).
        ctx.session.add(project)
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: theme sintetizado — "
                f"{len(theme['colors'])} colors, {len(theme['typography'])} fonts"
            ),
            outputs={
                "skipped": False,
                "colors": theme["colors"],
                "typography_keys": list(theme["typography"].keys()),
            },
        )


# ---------- Funciones puras (testeables sin BD) ----------


def synthesize_theme(computed: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Convierte el dict `{selector: {prop: value}}` en un Theme Styles
    estructurado. Pura — no toca BD ni session."""
    body = computed.get("body", {})
    button = computed.get("button") or computed.get(".wixui-button") or {}
    h1 = computed.get("h1", {})
    h2 = computed.get("h2", {})
    a_link = computed.get("a", {})

    return {
        "colors": {
            "bg": _color_or_default(body.get("background-color"), DEFAULT_BG),
            "text": _color_or_default(body.get("color"), DEFAULT_TEXT),
            "primary": _color_or_default(
                button.get("background-color"), DEFAULT_PRIMARY
            ),
            "accent": _color_or_default(a_link.get("color"), DEFAULT_ACCENT),
        },
        "typography": {
            "h1": _typography_dict(h1),
            "h2": _typography_dict(h2),
            "body": _typography_dict(body),
            "button": _typography_dict(button),
        },
        "spacing": {
            "section_y": DEFAULT_SECTION_PADDING_Y,
            "container_y": DEFAULT_CONTAINER_PADDING_Y,
        },
    }


def _color_or_default(value: str | None, default: str) -> str:
    """Normaliza un color CSS a hex. Devuelve `default` si:
    - value es None/empty
    - es 'transparent' o 'rgba(...,0)'
    - no parsea
    """
    if not value:
        return default
    v = value.strip().lower()
    if v in ("transparent", "none", "inherit", "initial"):
        return default
    if v.startswith("#"):
        return v
    m = _RE_RGB.match(v)
    if not m:
        return default
    r, g, b, a = m.groups()
    if a is not None and float(a) < 0.01:
        # rgba con alpha 0 → tratamos como transparente.
        return default
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _typography_dict(props: dict[str, str]) -> dict[str, str]:
    """Extrae solo las props tipográficas relevantes. Omite vacías."""
    result: dict[str, str] = {}
    for key in (
        "font-family", "font-size", "font-weight", "line-height", "text-align"
    ):
        if v := props.get(key):
            result[key] = v
    return result
