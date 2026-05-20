"""Extractor para webs Wix (Editor X, ADI, Studio).

Patrones consolidados en `.claude/skills/wix-extraction/SKILL.md`. Aquí
los codificamos como selectores y reglas de extracción concretas.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from wcm_scraper_core.extractors.base import ExtractedBlock, ExtractionResult
from wcm_types.enums import BlockType

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

    def hydration_wait_selector(self) -> str | None:
        # Espera a que el SITE_CONTAINER tenga mesh-id (proxy de hidratación Velo)
        return "#SITE_CONTAINER [data-mesh-id]"

    def hydration_extra_wait_ms(self) -> int:
        return 2000

    def extract(self, html: str, url: str) -> ExtractionResult:
        soup = BeautifulSoup(html, "lxml")
        result = ExtractionResult()

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
        for section in sections:
            block = self._classify_section(section)
            if block is None:
                continue
            block.order_index = order_index
            block.lang = result.page_lang
            result.blocks.append(block)
            order_index += 1

        # Detectar headers/footers
        if site_header := soup.find(id="SITE_HEADER"):
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
        if site_footer := soup.find(id="SITE_FOOTER"):
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

    def _classify_section(self, section: Tag) -> ExtractedBlock | None:
        """Clasifica un nodo `[data-mesh-id]` como un block_type."""
        # Heurística: si contiene heading + texto + CTA → hero
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
            return ExtractedBlock(
                block_type=BlockType.FORM,
                order_index=0,
                content_json={"fields": [], "notes": "Wix Forms — recrear en Gravity Forms"},
            )

        # Hero: h1 + button (típico)
        if has_h1 and has_button:
            return ExtractedBlock(
                block_type=BlockType.HERO,
                order_index=0,
                content_json=self._extract_hero(section),
            )

        # Sección con galería
        if section.find(class_=re.compile(r"wixui-pro-gallery|wixui-slideshow")):
            return ExtractedBlock(
                block_type=BlockType.GALLERY,
                order_index=0,
                content_json=self._extract_gallery(section),
            )

        # Faq (collapsible-text)
        if section.find(class_=re.compile(r"wixui-collapsible-text")):
            return ExtractedBlock(
                block_type=BlockType.FAQ,
                order_index=0,
                content_json=self._extract_faq(section),
            )

        # Heading puro
        if has_h2_or_h3 and not has_image and not has_button and not rich_text:
            heading = section.find(["h2", "h3"])
            return ExtractedBlock(
                block_type=BlockType.HEADING,
                order_index=0,
                content_json={"level": heading.name, "text": heading.get_text(strip=True)},
            )

        # Texto puro (rich-text)
        if rich_text and not has_image:
            return ExtractedBlock(
                block_type=BlockType.TEXT,
                order_index=0,
                content_json={"html": str(rich_text)[:10000]},
            )

        # Imagen + texto → bloque image (simplificado)
        if has_image and not has_button:
            img = section.find("img")
            return ExtractedBlock(
                block_type=BlockType.IMAGE,
                order_index=0,
                content_json={
                    "src": img.get("src") if img else None,
                    "alt": img.get("alt") if img else None,
                },
            )

        # No clasificado → unknown con sample de HTML para residual
        return ExtractedBlock(
            block_type=BlockType.UNKNOWN,
            order_index=0,
            content_json={"raw_html": str(section)[:3000]},
            notes="Wix section no clasificada en MVP",
        )

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
        # Filter Wix CDN
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
