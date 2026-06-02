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

        # v0.23.0 — `node_styles_json` (captura por nodo individual) da
        # acceso a paleta dinámica top-N + gradientes + multi-fonts.
        # Fallback al modo solo-global si no está disponible.
        node_styles = home.node_styles_json if isinstance(home.node_styles_json, list) else None
        theme = synthesize_theme(computed, node_styles=node_styles)
        project.theme_styles_origin = theme

        # v0.28.0 B11 — Catálogo canónico de Bricks Global Classes derivado
        # del theme. Sin esto, en `design_method=ai` la columna queda NULL
        # (RedesignAIAgent bypassa el transpiler) y el wp_deployer no
        # sube nada → cualquier `_cssGlobalClasses` que emita el LLM
        # apuntará a clases inexistentes en el WP destino.
        from wcm_bricks_transpiler import build_canonical_catalog  # noqa: PLC0415

        project.bricks_global_classes = build_canonical_catalog(theme)

        # Persistencia explicita (defensive: por si la session config no
        # autoflushea el mutación in-place del JSONB).
        ctx.session.add(project)
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: theme sintetizado — "
                f"{len(theme['colors'])} colors, {len(theme['typography'])} fonts, "
                f"{len(project.bricks_global_classes)} global classes canónicas"
            ),
            outputs={
                "skipped": False,
                "colors": theme["colors"],
                "typography_keys": list(theme["typography"].keys()),
                "global_classes_count": len(project.bricks_global_classes),
            },
        )


# ---------- Funciones puras (testeables sin BD) ----------


def synthesize_theme(
    computed: dict[str, dict[str, str]],
    *,
    node_styles: list[dict[str, Any]] | None = None,
    palette_size: int = 12,
) -> dict[str, Any]:
    """Convierte el dict `{selector: {prop: value}}` en un Theme Styles
    estructurado. Pura — no toca BD ni session.

    G.7 (2026-05-21) — limpia los font-family de cada selector eliminando
    identificadores Wix internos (`wfont_xxx`, `wf_xxx`) y mapea aliases
    `orig_xxx` a Google Fonts equivalentes. Recolecta la lista de Google
    Fonts a cargar en `google_fonts`.

    v0.23.0 — Si `node_styles` (captura por nodo del PlaywrightFetcher)
    está disponible, expande:
    - `colors`: paleta dinámica top-N (`palette_size`) de los colores
      más frecuentes en el origen, NO solo 4 slots fijos. Slots semánticos
      derivados por contexto (h1.color → "heading", button.bg → "primary"
      o "accent" según contraste).
    - `gradients`: lista de gradients detectados en background-image de
      cualquier nodo. Los mappers section los aplican via `_background`.
    - `google_fonts`: recolectados de TODOS los nodos (no solo
      body/h1/button), filtrando system fonts.
    """
    body = computed.get("body", {})
    button = computed.get("button") or computed.get(".wixui-button") or {}
    h1 = computed.get("h1", {})
    h2 = computed.get("h2", {})
    a_link = computed.get("a", {})

    typo_h1 = _typography_dict(h1)
    typo_h2 = _typography_dict(h2)
    typo_body = _typography_dict(body)
    typo_button = _typography_dict(button)

    google_fonts: set[str] = set()
    for typo in (typo_h1, typo_h2, typo_body, typo_button):
        if (raw := typo.get("font-family")):
            clean, gf = _clean_font_family(raw)
            typo["font-family"] = clean
            if gf:
                google_fonts.add(gf)

    # Slots base (4 fijos). Si tenemos node_styles, los ampliamos.
    colors: dict[str, str] = {
        "bg": _color_or_default(body.get("background-color"), DEFAULT_BG),
        "text": _color_or_default(body.get("color"), DEFAULT_TEXT),
        "primary": _color_or_default(
            button.get("background-color"), DEFAULT_PRIMARY
        ),
        "accent": _color_or_default(a_link.get("color"), DEFAULT_ACCENT),
    }
    gradients: list[str] = []

    if node_styles:
        # v0.23.0 — paleta top-N + gradientes + multi-fonts.
        palette_extra, grads = _extract_dynamic_palette(
            node_styles, palette_size=palette_size, base_colors=colors,
        )
        colors.update(palette_extra)
        gradients = grads

        # Recolectar fonts de TODOS los nodos.
        for node in node_styles:
            styles = node.get("styles") or {}
            if (raw := styles.get("font-family")):
                _clean, gf = _clean_font_family(raw)
                if gf:
                    google_fonts.add(gf)

    return {
        "colors": colors,
        "typography": {
            "h1": typo_h1,
            "h2": typo_h2,
            "body": typo_body,
            "button": typo_button,
        },
        "spacing": {
            "section_y": DEFAULT_SECTION_PADDING_Y,
            "container_y": DEFAULT_CONTAINER_PADDING_Y,
        },
        "google_fonts": sorted(google_fonts),
        "gradients": gradients,
    }


def _extract_dynamic_palette(
    node_styles: list[dict[str, Any]],
    *,
    palette_size: int,
    base_colors: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """v0.23.0 — Recolecta colores únicos del origen y devuelve:
    - `palette_extra: dict[slot, hex]` con slots `c1`, `c2`, ... `cN`
      (omitiendo los 4 base ya presentes en `base_colors`). Ordenados por
      frecuencia descendente.
    - `gradients: list[str]` con background-image gradients únicos.
    """
    from collections import Counter

    color_counter: Counter[str] = Counter()
    gradients_seen: set[str] = set()
    base_values = {v.lower() for v in base_colors.values()}

    for node in node_styles:
        styles = node.get("styles") or {}
        for prop in ("color", "background-color"):
            v = styles.get(prop)
            if not v:
                continue
            hex_val = _color_or_default(v, "")
            if hex_val and hex_val.lower() not in base_values:
                color_counter[hex_val.lower()] += 1
        bg = styles.get("background-image", "")
        if "gradient" in bg.lower():
            gradients_seen.add(bg.strip())

    palette_extra: dict[str, str] = {}
    # Reservar 4 slots para los base; los nuevos slots empiezan en c1.
    remaining = max(0, palette_size - len(base_colors))
    for idx, (hex_val, _count) in enumerate(color_counter.most_common(remaining), start=1):
        palette_extra[f"c{idx}"] = hex_val

    return palette_extra, sorted(gradients_seen)


# ---------- G.7 — Font cleaning ----------

#: Mapping de aliases Wix conocidos a Google Fonts equivalentes. Las
#: fonts Wix internas tienen 3 capas (wfont_hash, wf_hash, orig_name).
#: Nos quedamos con el alias humano (`orig_xxx`) y mapeamos a una
#: Google Font cercana visualmente. La lista no es exhaustiva — fallback
#: a `Inter` para sans desconocidas y `Playfair Display` para serif.
_WIX_TO_GOOGLE_FONT: dict[str, str] = {
    "orig_albra_sans_light": "Inter",
    "orig_albra_sans_regular": "Inter",
    "orig_neue_montreal_regular": "Inter",
    "orig_neue_montreal_light": "Inter",
    "orig_playfair_display_regular": "Playfair Display",
    "orig_playfair_display_italic": "Playfair Display",
    "orig_inter_regular": "Inter",
    "orig_inter_bold": "Inter",
    "orig_montserrat_regular": "Montserrat",
    "orig_montserrat_bold": "Montserrat",
    "orig_poppins_regular": "Poppins",
    "orig_poppins_bold": "Poppins",
    "orig_roboto_regular": "Roboto",
    "orig_open_sans_regular": "Open Sans",
    "orig_lato_regular": "Lato",
    "orig_merriweather_regular": "Merriweather",
    "orig_georgia_regular": "Georgia",  # fallback to system
    "orig_helvetica_neue_regular": "Inter",
}

#: Fuentes "del sistema" — NO se cargan vía Google Fonts (ya están en el OS).
_SYSTEM_FONTS: frozenset[str] = frozenset({
    "arial", "helvetica", "helvetica neue", "times", "times new roman",
    "georgia", "courier", "courier new", "verdana", "tahoma",
    "trebuchet ms", "system-ui", "-apple-system", "blinkmacsystemfont",
    "sans-serif", "serif", "monospace", "cursive", "fantasy",
    "ui-sans-serif", "ui-serif", "ui-monospace",
})


def _clean_font_family(raw: str) -> tuple[str, str | None]:
    """Limpia un valor `font-family` capturado del computed style.

    Devuelve `(clean_value, google_font_name | None)`:
    - `clean_value`: string para inyectar en Bricks (sin Wix internals).
    - `google_font_name`: family a cargar vía Google Fonts (None si es
      del sistema o no mappable).

    Ejemplos:
    - `"wfont_d0a698_8cd9dd45..., wf_8cd9dd45..., orig_albra_sans_light"`
      → `("Inter, sans-serif", "Inter")`
    - `"Arial, Helvetica, sans-serif"` → `("Arial, Helvetica, sans-serif", None)`
    - `"Inter, sans-serif"` → `("Inter, sans-serif", "Inter")`
    """
    if not raw:
        return raw, None

    # Split por coma + trim de comillas y espacios.
    parts = [p.strip().strip("'\"") for p in raw.split(",")]
    # Filtrar Wix internals `wfont_xxx` y `wf_xxx`.
    parts = [p for p in parts if not p.startswith(("wfont_", "wf_"))]

    google: str | None = None

    # Resolver el primer alias `orig_xxx` a Google Font si lo tenemos.
    new_parts: list[str] = []
    for p in parts:
        if p.startswith("orig_"):
            mapped = _WIX_TO_GOOGLE_FONT.get(p)
            if mapped:
                new_parts.append(mapped)
                if google is None:
                    google = mapped
            # Si no está en el mapping, ignoramos el alias `orig_` y
            # caemos al siguiente fallback de la cadena.
            continue
        new_parts.append(p)

    if not new_parts:
        new_parts = ["sans-serif"]

    # Si la primera no-system family no se ha marcado como Google ya, ver
    # si es alguna conocida (caso: la web ya usa Inter directamente).
    if google is None:
        first = new_parts[0].lower()
        if first not in _SYSTEM_FONTS:
            # Asumimos que es una Google Font (mejor falso positivo que
            # falsos negativos — Bricks se queja silenciosamente si no
            # carga, pero el operador verá su font).
            google = new_parts[0]

    return ", ".join(new_parts), google


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
