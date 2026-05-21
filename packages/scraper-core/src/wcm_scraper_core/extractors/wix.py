"""Extractor para webs Wix (Editor X, ADI, Studio).

Patrones consolidados en `.claude/skills/wix-extraction/SKILL.md`. Aquí
los codificamos como selectores y reglas de extracción concretas.
"""

from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup, Tag

from wcm_scraper_core.extractors.base import ExtractedBlock, ExtractionResult
from wcm_types.enums import BlockType

log = logging.getLogger("wcm.scraper_core.extractors.wix")

#: CDN Wix base para imágenes. Cada `<wow-image data-image-info>` contiene
#: un `imageData.uri` relativo (`11062b_xxx~mv2.png`) que se sirve desde
#: `https://static.wixstatic.com/media/{uri}`.
WIX_MEDIA_CDN = "https://static.wixstatic.com/media/"

#: Componentes Wix → BlockType del dominio.
WIX_COMPONENT_MAP: dict[str, BlockType] = {
    "wixui-button": BlockType.CTA,
    "wixui-rich-text": BlockType.TEXT,
    "wixui-pro-gallery": BlockType.GALLERY,
    "wixui-slideshow": BlockType.GALLERY,  # carousel
    "wixui-repeater": BlockType.UNKNOWN,  # decisión por repeater individual
    "wixui-vector-image": BlockType.IMAGE,
    "wixui-image": BlockType.IMAGE,
    "wixui-collapsible-text": BlockType.FAQ,
}

# Atributos a sanitizar (tracking, debug)
_SANITIZE_ATTRS = ("data-wix-bi", "data-wix-perf", "data-mesh-id-debug")


class WixExtractor:
    builder_name = "wix"

    def __init__(self) -> None:
        #: v0.23.0 — Índice `node_path → styles` poblado al inicio de
        #: `extract()` cuando el caller pasa `node_styles`. Lo consulta
        #: `_enrich_with_styles` tras crear cada ExtractedBlock para
        #: asignar `element_styles` + `node_path`.
        self._node_styles_index: dict[str, dict[str, str]] | None = None

    def hydration_wait_selector(self) -> str | None:
        # Espera a que el SITE_CONTAINER tenga mesh-id (proxy de hidratación Velo)
        return "#SITE_CONTAINER [data-mesh-id]"

    def hydration_extra_wait_ms(self) -> int:
        return 2000

    def extract(
        self,
        html: str,
        url: str,
        *,
        node_styles: list[dict] | None = None,
    ) -> ExtractionResult:
        """Extrae bloques semánticos.

        v0.23.0 — `node_styles` (de `FetchResult.node_styles`) permite
        enriquecer cada bloque con sus computed styles del origen via
        matching por `node_path`. Si es None, los bloques salen sin
        `element_styles` (compat backward).
        """
        soup = BeautifulSoup(html, "lxml")
        result = ExtractionResult()
        self._node_styles_index = (
            {entry["node_path"]: entry.get("styles", {}) for entry in node_styles}
            if node_styles
            else None
        )

        # Meta básica
        if (html_tag := soup.find("html")) and html_tag.get("lang"):
            result.page_lang = str(html_tag.get("lang"))
        if (title_tag := soup.find("title")) and title_tag.string:
            result.page_title = title_tag.string.strip()

        # Recolección de classes para diagnóstico
        for el in soup.find_all(class_=True):
            for cls in el.get("class", []):
                if cls.startswith(("wixui-", "comp-")):
                    result.detected_classes.add(cls)

        # Identificar secciones top-level. Wix tiene 2 layouts según editor:
        # - Wix Studio/Mesh moderno → componentes con atributo `data-mesh-id`
        # - Wix Editor clásico (sites pre-Studio) → <section> HTML con
        #   `id="comp-XXX"`. NO usan data-mesh-id, así que ese selector
        #   devuelve 0 elementos y necesitamos fallback.
        sections = soup.find_all(attrs={"data-mesh-id": True})
        if not sections:
            # Fallback Wix Editor clásico: <section> con id="comp-..." son
            # los containers top-level. El _classify_section es agnóstico al
            # atributo de origen (clasifica por h1/h2/button/img), así que
            # funciona con cualquier sección semántica.
            sections = [
                s for s in soup.find_all("section")
                if isinstance(s.get("id"), str) and s.get("id", "").startswith("comp-")
            ]
        order_index = 0
        section_idx = 0  # AI.1 — índice DOM de sección top-level
        nav_detected = False
        footer_detected = False
        for section in sections:
            classes = section.get("class") or []
            # B.2 — Wix Editor clásico: el header es una `<section>` con
            # clase `wixui-header` (no `id="SITE_HEADER"` como Wix Studio).
            # Detectarlo aquí evita que el classify lo marque UNKNOWN.
            if "wixui-header" in classes:
                if not nav_detected:
                    result.blocks.insert(
                        0,
                        ExtractedBlock(
                            block_type=BlockType.NAV,
                            order_index=-1,
                            content_json={"raw_html": str(section)[:5000]},
                            lang=result.page_lang,
                            notes=(
                                "Wix Editor clásico wixui-header — "
                                "reconstruir nav-menu en destino"
                            ),
                        ),
                    )
                    nav_detected = True
                continue
            # B.3 — Footer equivalente: `<section class="wixui-footer">`.
            if "wixui-footer" in classes:
                if not footer_detected:
                    result.blocks.append(
                        ExtractedBlock(
                            block_type=BlockType.FOOTER,
                            order_index=order_index,
                            content_json={"raw_html": str(section)[:5000]},
                            lang=result.page_lang,
                            notes="Wix Editor clásico wixui-footer",
                        )
                    )
                    footer_detected = True
                    order_index += 1
                continue
            # G.1 (2026-05-21) — `_classify_section` puede devolver
            # múltiples bloques cuando la sección lleva varios elementos
            # textuales (caso real: "What this solves" con h2 + p + ul).
            # Antes solo emitíamos UN bloque (el primer rich-text) y se
            # perdía ~50% del contenido en secciones de texto.
            section_blocks = self._classify_section(section)
            # AI.1 — calcular coverage_score por sección: chars de texto
            # extraído / chars de texto total en la sección. <0.6 marca
            # candidatos a AI vision en AiAssistAgent.
            section_text_total = len(section.get_text(strip=True))
            section_text_captured = sum(
                len(self._extracted_text_for_block(b))
                for b in section_blocks
            )
            coverage = (
                section_text_captured / max(section_text_total, 1)
                if section_text_total
                else 1.0
            )
            for block in section_blocks:
                block.order_index = order_index
                block.lang = result.page_lang
                block.section_idx = section_idx
                # cap a 1.0 (puede pasar de 1 por whitespace ajustes)
                block.coverage_score = min(1.0, coverage)
                result.blocks.append(block)
                order_index += 1
            section_idx += 1

        # Wix Studio: header/footer por `id="SITE_HEADER"`/`SITE_FOOTER`
        # (formato moderno). Solo se aplica si no detectamos ya el
        # equivalente de Editor clásico, para no duplicar.
        if not nav_detected and (site_header := soup.find(id="SITE_HEADER")):
            result.blocks.insert(
                0,
                ExtractedBlock(
                    block_type=BlockType.NAV,
                    order_index=-1,
                    content_json={"raw_html": str(site_header)[:5000]},
                    lang=result.page_lang,
                    notes="Wix SITE_HEADER — reconstruir nav-menu en destino",
                ),
            )
        if not footer_detected and (site_footer := soup.find(id="SITE_FOOTER")):
            result.blocks.append(
                ExtractedBlock(
                    block_type=BlockType.FOOTER,
                    order_index=order_index,
                    content_json={"raw_html": str(site_footer)[:5000]},
                    lang=result.page_lang,
                    notes="Wix SITE_FOOTER",
                )
            )
            order_index += 1

        # Renumerar para asegurar orden ascendente sin huecos negativos
        result.blocks.sort(key=lambda b: b.order_index)
        for i, b in enumerate(result.blocks):
            b.order_index = i

        # Assets
        result.asset_urls = self._extract_image_urls(soup)
        result.font_urls = self._extract_font_urls(html)
        result.video_urls = self._extract_video_urls(soup)

        return result

    # ---------- helpers ----------

    def _classify_section(self, section: Tag) -> list[ExtractedBlock]:
        """Clasifica una sección y devuelve la lista de bloques que produce.

        G.1 (2026-05-21) — devuelve `list[ExtractedBlock]` (antes era
        `ExtractedBlock | None`). Las secciones de texto ricas (h2 + p +
        ul) ahora emiten varios bloques en lugar de uno solo truncado.
        Devuelve lista vacía si la sección no produce ningún bloque
        útil (caso edge: section vacío sin contenido).
        """
        has_h1 = section.find(["h1"]) is not None
        has_h2_or_h3 = section.find(["h2", "h3"]) is not None
        has_button = bool(section.find(class_=re.compile(r"wixui-button")))
        has_image = bool(section.find(["img"]))
        # Form: <form> directo en la sección o data-mesh-id que mencione 'form'
        has_form = bool(section.find("form")) or "form" in (
            section.get("data-mesh-id") or ""
        ).lower()
        rich_text = section.find(class_=re.compile(r"wixui-rich-text"))

        # Forms
        if has_form:
            return [ExtractedBlock(
                block_type=BlockType.FORM,
                order_index=0,
                content_json={"fields": [], "notes": "Wix Forms — recrear en Gravity Forms"},
            )]

        # Hero: h1 + button (típico)
        if has_h1 and has_button:
            return [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.HERO,
                    order_index=0,
                    content_json=self._extract_hero(section),
                ),
                section,
            )]

        # Sección con galería
        if section.find(class_=re.compile(r"wixui-pro-gallery|wixui-slideshow")):
            return [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.GALLERY,
                    order_index=0,
                    content_json=self._extract_gallery(section),
                ),
                section,
            )]

        # B.4 — Sección con `wixui-repeater`: lista/grid de items
        # repetidos (case-studies, servicios, testimonios). Antes caía
        # a UNKNOWN porque no había mapping. Caso real: "Selected work"
        # en mariya.design con 3 case-studies.
        if section.find(class_=re.compile(r"wixui-repeater")):
            return [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.GRID,
                    order_index=0,
                    content_json=self._extract_grid(section),
                ),
                section,
            )]

        # Faq (collapsible-text)
        if section.find(class_=re.compile(r"wixui-collapsible-text")):
            return [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.FAQ,
                    order_index=0,
                    content_json=self._extract_faq(section),
                ),
                section,
            )]

        # G.1 — Secciones con uno o varios rich-text: extraer TODO el
        # contenido textual como bloques separados (heading + text + ul).
        # Antes solo cogíamos el primer rich-text como un bloque TEXT con
        # HTML opaco → "What this solves" salía solo como h2 sin la lista
        # de bullets. Ahora cada h1-h6, p, ul, ol del rich-text se emite
        # como un bloque atómico que los mappers ya conocen.
        if rich_text and not has_image:
            blocks = self._extract_text_blocks(section)
            if blocks:
                return blocks

        # Heading puro fuera de rich-text (edge case raro).
        if has_h2_or_h3 and not has_image and not has_button and not rich_text:
            heading = section.find(["h2", "h3"])
            return [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.HEADING,
                    order_index=0,
                    content_json={
                        "level": heading.name,
                        "text": heading.get_text(strip=True),
                    },
                ),
                heading,
            )]

        # Imagen + texto → bloque image (simplificado).
        # Si además hay rich-text, también extraemos los textos.
        if has_image and not has_button:
            img = section.find("img")
            blocks: list[ExtractedBlock] = [self._enrich_with_styles(
                ExtractedBlock(
                    block_type=BlockType.IMAGE,
                    order_index=0,
                    content_json={
                        "src": img.get("src") if img else None,
                        "alt": img.get("alt") if img else None,
                    },
                ),
                img if img is not None else section,
            )]
            if rich_text:
                blocks.extend(self._extract_text_blocks(section))
            return blocks

        # No clasificado → unknown con sample de HTML para residual
        return [ExtractedBlock(
            block_type=BlockType.UNKNOWN,
            order_index=0,
            content_json={"raw_html": str(section)[:3000]},
            notes="Wix section no clasificada en MVP",
        )]

    _TEXTUAL_TAGS: frozenset[str] = frozenset({
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol",
    })

    @staticmethod
    def _extracted_text_for_block(block: ExtractedBlock) -> str:
        """AI.1 — estima la cantidad de texto que el bloque "ocupa" del
        origen. Usado para `coverage_score`. No exacto pero suficiente
        para distinguir secciones bien extraídas (~100%) de pobres (<60%)."""
        cj = block.content_json or {}
        for key in ("text", "headline", "html"):
            v = cj.get(key)
            if isinstance(v, str):
                return v
        return ""

    def _extract_text_blocks(self, section: Tag) -> list[ExtractedBlock]:
        """G.1 — Extrae bloques atómicos (heading, text, list) del
        contenido textual de la sección.

        Recorre toda la sección buscando elementos textuales `<h1>-<h6>`,
        `<p>`, `<ul>`, `<ol>` (DENTRO o FUERA de `wixui-rich-text`,
        porque Wix a veces envuelve cada elemento textual en su propio
        rich-text individual). Cada uno emite un bloque atómico:
        - heading → `BlockType.HEADING` con level + text
        - p / ul / ol → `BlockType.TEXT` con html preservado

        Dedupe por elemento exacto: si un `<h2>` ESTÁ dentro de un
        `<p.wixui-rich-text>`, NO lo procesamos dos veces (la cadena de
        find_all sobre section ya los iteraría ambos).
        """
        out: list[ExtractedBlock] = []
        # Recorrer la sección completa en orden DOM. find_all sin
        # recursive=False itera profundidad.
        for el in section.find_all(list(self._TEXTUAL_TAGS), recursive=True):
            tag = el.name
            # Skip si está anidado dentro de OTRO elemento textual ya
            # iterado (caso real: <h2> dentro de <p.wixui-rich-text>).
            # Bs4 no tiene un "already-seen" set fiable, así que
            # comprobamos ancestros: si el primer ancestor textual NO
            # es el propio nodo, lo omitimos (su padre ya lo cubrirá).
            ancestor_textual = self._first_textual_ancestor(el, section)
            if ancestor_textual is not None and ancestor_textual is not el:
                continue
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                text = el.get_text(strip=True)
                if not text:
                    continue
                out.append(self._enrich_with_styles(
                    ExtractedBlock(
                        block_type=BlockType.HEADING,
                        order_index=0,
                        content_json={"level": tag, "text": text},
                    ),
                    el,
                ))
            elif tag == "p":
                text = el.get_text(strip=True)
                if not text:
                    continue
                out.append(self._enrich_with_styles(
                    ExtractedBlock(
                        block_type=BlockType.TEXT,
                        order_index=0,
                        content_json={"html": str(el)[:5000]},
                    ),
                    el,
                ))
            elif tag in ("ul", "ol"):
                items_text = " ".join(
                    li.get_text(strip=True) for li in el.find_all("li")
                )
                if not items_text:
                    continue
                out.append(self._enrich_with_styles(
                    ExtractedBlock(
                        block_type=BlockType.TEXT,
                        order_index=0,
                        content_json={"html": str(el)[:5000]},
                    ),
                    el,
                ))
        return out

    # ----- v0.23.0: node_path + element_styles -----

    def _node_path(self, el: Tag, max_depth: int = 6) -> str:
        """Calcula ruta DOM determinista del nodo, equivalente al JS
        `nodePath` de `playwright_fetcher._CAPTURE_NODE_STYLES_JS`. Sin
        esto el matching contra `node_styles_index` no funciona.
        """
        parts: list[str] = []
        cur: Tag | None = el
        depth = 0
        while cur is not None and getattr(cur, "name", None) and cur.name != "body" and depth < max_depth:
            tag = cur.name
            mesh = cur.get("data-mesh-id") if hasattr(cur, "get") else None
            cur_id = cur.get("id") if hasattr(cur, "get") else None
            if mesh:
                parts.insert(0, f'{tag}[data-mesh-id="{mesh}"]')
            elif cur_id:
                parts.insert(0, f"{tag}#{cur_id}")
            else:
                parent = cur.parent
                if parent is not None and hasattr(parent, "children"):
                    sibs = [s for s in parent.children if getattr(s, "name", None) == tag]
                    try:
                        idx = sibs.index(cur)
                        parts.insert(0, f"{tag}:nth-of-type({idx + 1})")
                    except ValueError:
                        parts.insert(0, tag)
                else:
                    parts.insert(0, tag)
            cur = cur.parent
            depth += 1
        return " > ".join(parts)

    def _enrich_with_styles(self, block: ExtractedBlock, tag: Tag) -> ExtractedBlock:
        """Asigna `node_path` + `element_styles` al bloque si tenemos
        el índice. Mutate-and-return idiom para encadenar en append."""
        if self._node_styles_index is None:
            return block
        path = self._node_path(tag)
        block.node_path = path
        styles = self._node_styles_index.get(path)
        if styles:
            block.element_styles = dict(styles)
        return block

    def _first_textual_ancestor(
        self, el: Tag, stop_at: Tag
    ) -> Tag | None:
        """Devuelve el ancestor más cercano que es un elemento textual,
        o el propio `el` si lo es. None si no hay ninguno hasta `stop_at`.
        """
        cur: Tag | None = el
        while cur is not None and cur is not stop_at:
            if cur.name in self._TEXTUAL_TAGS:
                return cur
            cur = cur.parent
        return None

    def _extract_hero(self, section: Tag) -> dict:
        h1 = section.find("h1")
        sub = section.find(["h2", "h3", "p"])
        button = section.find(class_=re.compile(r"wixui-button"))
        return {
            "headline": h1.get_text(strip=True) if h1 else None,
            "subheadline": sub.get_text(strip=True) if sub and sub != h1 else None,
            "cta_text": button.get_text(strip=True) if button else None,
            "cta_url": (button.find("a") or {}).get("href") if button else None,
            "bg_color": None,  # se inferiría de CSS computado en runtime real
        }

    def _extract_gallery(self, section: Tag) -> dict:
        imgs = section.find_all("img")
        return {
            "asset_ids": [],  # se rellenan tras asset_resolver
            "image_urls": [img.get("src") for img in imgs if img.get("src")],
            "layout": "carousel" if section.find(class_=re.compile(r"slideshow")) else "grid",
        }

    def _extract_grid(self, section: Tag) -> dict:
        """Extrae los items de un `wixui-repeater` como lista de cards.

        Cada item del repeater es un elemento con role="listitem" o con
        la clase `wixui-repeater__item`. De cada uno extraemos:
        - imagen (url del CDN Wix vía wow-image data-image-info, fallback a img src)
        - heading (h1/h2/h3 dentro del item)
        - link (primer <a href> dentro del item)

        Las URLs de imagen también se exponen en `result.asset_urls` por
        `_extract_image_urls` (que ya itera todos los wow-image del DOM).
        """
        items: list[dict] = []
        item_nodes = section.find_all(
            class_=re.compile(r"wixui-repeater__item")
        ) or section.find_all(attrs={"role": "listitem"})
        for item in item_nodes:
            heading_tag = item.find(["h1", "h2", "h3", "h4"])
            link_tag = item.find("a", href=True)
            img_url: str | None = None
            # Preferir wow-image (URL real) sobre <img src> (puede ser vacío).
            wow = item.find("wow-image")
            if wow and wow.get("data-image-info"):
                img_url = _wix_uri_from_data_info(wow["data-image-info"])
            if img_url is None:
                img_tag = item.find("img")
                if img_tag and img_tag.get("src"):
                    img_url = img_tag["src"]
            items.append({
                "heading": heading_tag.get_text(strip=True) if heading_tag else None,
                "link": link_tag.get("href") if link_tag else None,
                "image_url": img_url,
            })
        return {
            "items": items,
            "layout": "grid",
            "notes": (
                "Wix repeater — reconstruir en destino como Bricks Pricing / "
                "Image Cards / Loop. El operador valida el layout final."
            ),
        }

    def _extract_faq(self, section: Tag) -> dict:
        items: list[dict] = []
        for collapsible in section.find_all(class_=re.compile(r"wixui-collapsible-text")):
            q = collapsible.find(["button", "summary"])
            a = collapsible.find(class_=re.compile(r"collapsible-text-content|wixui-rich-text"))
            if q:
                items.append(
                    {
                        "q": q.get_text(strip=True),
                        "a": a.get_text(strip=True) if a else "",
                    }
                )
        return {"items": items}

    def _extract_image_urls(self, soup: BeautifulSoup) -> list[str]:
        urls: set[str] = set()
        for img in soup.find_all("img"):
            for attr in ("src", "data-src"):
                if val := img.get(attr):
                    urls.add(val)
            if srcset := img.get("srcset"):
                for entry in srcset.split(","):
                    candidate = entry.strip().split(" ", 1)[0]
                    if candidate:
                        urls.add(candidate)
        # B.5 — `<wow-image>` es el wrapper habitual de Wix moderno
        # (Editor clásico y Studio). El src del <img> interno puede
        # estar vacío hasta que JS hidrata, pero `data-image-info`
        # siempre tiene el URI original del CDN.
        for wow in soup.find_all("wow-image"):
            info_raw = wow.get("data-image-info")
            if not info_raw:
                continue
            url = _wix_uri_from_data_info(info_raw)
            if url:
                urls.add(url)
        return sorted(u for u in urls if u.startswith(("http", "//")))

    def _extract_font_urls(self, html: str) -> list[str]:
        # @font-face src: url("..."), Google Fonts
        urls = set(re.findall(r'src:\s*url\(["\']?([^"\')]+)["\']?\)', html))
        urls.update(re.findall(r'https?://fonts\.googleapis\.com/[^"\']+', html))
        return sorted(urls)

    def _extract_video_urls(self, soup: BeautifulSoup) -> list[str]:
        urls: set[str] = set()
        for v in soup.find_all("video"):
            if src := v.get("src"):
                urls.add(src)
            for source in v.find_all("source"):
                if src := source.get("src"):
                    urls.add(src)
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "youtube" in src or "vimeo" in src:
                urls.add(src)
        return sorted(urls)


def _wix_uri_from_data_info(info_raw: str) -> str | None:
    """Parsea el JSON de `wow-image data-image-info` y devuelve la URL
    absoluta en el CDN Wix, o None si el formato no es esperado.

    Formato típico (algunos campos pueden faltar):
        {"containerId":"...","displayMode":"fit","encoding":"AVIF",
         "imageData":{"width":200,"height":200,
                      "uri":"11062b_xxx~mv2.png","name":"","displayMode":"fit"}}
    """
    try:
        data = json.loads(info_raw)
    except (json.JSONDecodeError, TypeError):
        log.debug("wix_wow_image_invalid_json", extra={"info_raw_head": info_raw[:80]})
        return None
    image_data = data.get("imageData") if isinstance(data, dict) else None
    if not isinstance(image_data, dict):
        return None
    uri = image_data.get("uri")
    if not isinstance(uri, str) or not uri:
        return None
    # uri puede venir ya como URL absoluta (raro) o como filename relativo.
    if uri.startswith(("http://", "https://")):
        return uri
    return f"{WIX_MEDIA_CDN}{uri}"
