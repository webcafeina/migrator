"""Drive de estados ocultos en componentes interactivos (Sprint v0.24.0 DS).

Slideshows, tabs y accordions Wix Studio renderizan client-side y por
defecto solo se ve el estado activo. WixScraper (referencia técnica)
demostró que clicar entre estados + capturar `innerHTML` por estado
permite recuperar el contenido oculto.

Este módulo encapsula la lógica de:
- `extract_slideshow_states(html)`: parsea HTML hidratado para detectar
  un slideshow Wix y extraer estados que YA estén en el DOM (slides
  como sub-`<div>` de `[data-testid="slidesWrapper"]`).
- `extract_tabs_states(html)`: detecta `[role="tablist"]` + paneles.
- `extract_accordion_states(html)`: detecta `[aria-expanded]` con
  panel asociado.

Diseño:
- **MVP estático**: solo extrae estados YA presentes en el DOM
  hidratado (Wix Studio suele renderizar todos los slides con
  `display: none`/`opacity: 0` en lugar de removerlos).
- **Drive real Playwright** (clic+wait) queda como extensión futura
  via `playwright_fetcher.drive_states()` cuando el operador detecte
  que un origen NO renderiza todos los estados estáticamente.

Selectores documentados en WixScraper + `docs/referencias/h2b-skill/`:
- Slideshow: `.wixui-slideshow`, `[data-testid="slidesWrapper"]`, hijos
  inmediatos = slides.
- Tabs: `[role="tablist"]` + `[role="tab"]` + `[role="tabpanel"]` con
  `aria-controls` / `aria-labelledby` para asociar.
- Accordion: `.wixui-collapsible-text` o `[aria-expanded]` + sibling
  panel.

Fallbacks múltiples: si el selector primario no aparece, intentar
patrones swiper/slick (`.swiper-slide`, `.slick-slide`) que Wix usa
en algunos templates antiguos.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Tag

# ---------- Selectores Wix Studio ----------

#: Selectores combinados Wix + Webflow + Hostinger AI.
#: v0.24.0 MB añade `.w-slider` (Webflow) y `.hi-slider` (Hostinger).
_SLIDESHOW_SELECTORS = (
    ".wixui-slideshow",
    "[data-testid='slidesWrapper']",
    ".w-slider",
    ".hi-slider",
)

_SLIDE_CHILD_SELECTORS = (
    "[data-testid='slidesWrapper'] > div",
    ".swiper-slide",
    ".slick-slide",
    ".w-slide",
    ".hi-slide",
)

_TABLIST_SELECTORS = (
    "[role='tablist']",
    ".wixui-tabs",
    ".w-tab-menu",
    ".hi-tabs",
)

_TAB_SELECTORS = (
    "[role='tab']",
    ".w-tab-link",
)

_TABPANEL_SELECTORS = (
    "[role='tabpanel']",
    ".w-tab-pane",
)

_ACCORDION_SELECTORS = (
    ".wixui-collapsible-text",
    "[role='button'][aria-expanded]",
    ".w-dropdown",
)


def _find_first_matching(soup: BeautifulSoup | Tag, selectors: tuple[str, ...]) -> Tag | None:
    """Devuelve el primer elemento que matchee cualquiera de los
    selectores. None si ninguno."""
    for sel in selectors:
        el = soup.select_one(sel)
        if el is not None:
            return el
    return None


def _find_all_matching(soup: BeautifulSoup | Tag, selectors: tuple[str, ...]) -> list[Tag]:
    """Devuelve TODOS los elementos que matcheen cualquiera de los
    selectores (deduplicados)."""
    seen: set[int] = set()
    out: list[Tag] = []
    for sel in selectors:
        for el in soup.select(sel):
            if id(el) not in seen:
                seen.add(id(el))
                out.append(el)
    return out


# ---------- Extractores ----------


def extract_slideshow_states(section_or_html: Tag | str) -> list[dict[str, Any]]:
    """Devuelve `[{idx, html}]` con cada slide del slideshow detectado.

    `section_or_html` puede ser un Tag (ya parseado) o string HTML.
    Si no detecta slideshow, devuelve lista vacía.

    Estrategia:
    1. Busca `data-testid="slidesWrapper"` o `.wixui-slideshow`.
    2. Sus hijos directos (`> div`, `.swiper-slide`, `.slick-slide`)
       son los slides.
    3. Captura `outerHTML` de cada slide.

    Cap a 20 slides para evitar patológicos.
    """
    container = _ensure_tag(section_or_html)
    if container is None:
        return []
    slideshow = _find_first_matching(container, _SLIDESHOW_SELECTORS)
    if slideshow is None:
        return []
    # Buscar slides hijos.
    slides = _find_all_matching(slideshow, _SLIDE_CHILD_SELECTORS)
    if not slides:
        # Fallback: hijos directos div del slideshow.
        slides = [c for c in slideshow.find_all("div", recursive=False)]
    if not slides:
        return []
    out: list[dict[str, Any]] = []
    for idx, slide in enumerate(slides[:20]):
        out.append({
            "idx": idx,
            "html": str(slide)[:5000],
        })
    return out


def extract_tabs_states(section_or_html: Tag | str) -> list[dict[str, Any]]:
    """Devuelve `[{idx, label, content_html}]` con cada tab+panel detectado.

    Asocia tab → panel via `aria-controls` (id del panel) o por orden DOM.
    Cap a 10 tabs.
    """
    container = _ensure_tag(section_or_html)
    if container is None:
        return []
    tablist = _find_first_matching(container, _TABLIST_SELECTORS)
    if tablist is None:
        return []
    tabs = _find_all_matching(tablist, _TAB_SELECTORS)
    if not tabs:
        return []
    # Buscar tabpanels en TODA la section (los paneles están fuera del tablist).
    panels = _find_all_matching(container, _TABPANEL_SELECTORS)
    panels_by_id: dict[str, Tag] = {p.get("id"): p for p in panels if p.get("id")}

    out: list[dict[str, Any]] = []
    for idx, tab in enumerate(tabs[:10]):
        label = tab.get_text(strip=True)[:200]
        controls_id = tab.get("aria-controls")
        panel = panels_by_id.get(controls_id) if controls_id else None
        if panel is None and idx < len(panels):
            panel = panels[idx]
        content_html = str(panel)[:5000] if panel else ""
        out.append({
            "idx": idx,
            "label": label,
            "content_html": content_html,
        })
    return out


def extract_accordion_states(section_or_html: Tag | str) -> list[dict[str, Any]]:
    """Devuelve `[{idx, title, content_html}]` con cada panel accordion.

    Estrategia Wix:
    - `.wixui-collapsible-text` items con title + content.
    - Fallback: `[aria-expanded]` con next sibling panel.
    """
    container = _ensure_tag(section_or_html)
    if container is None:
        return []
    items = _find_all_matching(container, _ACCORDION_SELECTORS)
    if not items:
        return []
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items[:15]):
        # Buscar title (h2-h4 dentro o el propio text del trigger)
        title_el = item.find(["h2", "h3", "h4", "h5", "button"])
        title = title_el.get_text(strip=True)[:200] if title_el else item.get_text(strip=True)[:200]
        # Content: siguiente hermano o panel referenciado.
        content_el = item.find_next_sibling()
        if content_el is None:
            content_el = item.find(class_=lambda c: c and ("content" in c or "panel" in c))
        content_html = str(content_el)[:5000] if content_el else ""
        out.append({
            "idx": idx,
            "title": title,
            "content_html": content_html,
        })
    return out


def _ensure_tag(value: Tag | str | None) -> Tag | None:
    """Convierte string HTML a Tag (parseando) o devuelve Tag tal cual."""
    if value is None:
        return None
    if isinstance(value, Tag):
        return value
    if isinstance(value, str):
        soup = BeautifulSoup(value, "lxml")
        return soup
    return None
