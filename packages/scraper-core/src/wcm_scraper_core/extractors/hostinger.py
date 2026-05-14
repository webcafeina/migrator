"""Extractor para webs Hostinger AI Builder (incluye legado Zyro).

Ventaja vs Wix/Webflow: Hostinger AI Builder etiqueta cada sección con
`data-block-type` (hero, text, image, gallery, cta, form, testimonial,
faq, pricing). Eso permite mapping casi 1:1 a nuestro BlockType.

Patrones documentados en `.claude/skills/hostinger-ai-extraction/SKILL.md`.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from wcm_scraper_core.extractors.base import ExtractedBlock, ExtractionResult
from wcm_types.enums import BlockType

#: Mapping directo Hostinger data-block-type → nuestro BlockType.
HOSTINGER_BLOCK_MAP: dict[str, BlockType] = {
    "hero": BlockType.HERO,
    "text": BlockType.TEXT,
    "heading": BlockType.HEADING,
    "image": BlockType.IMAGE,
    "gallery": BlockType.GALLERY,
    "cta": BlockType.CTA,
    "form": BlockType.FORM,
    "testimonial": BlockType.TESTIMONIAL,
    "pricing": BlockType.PRICING,
    "faq": BlockType.FAQ,
    "video": BlockType.VIDEO,
    "divider": BlockType.DIVIDER,
    "footer": BlockType.FOOTER,
    "nav": BlockType.NAV,
}


class HostingerExtractor:
    builder_name = "hostinger_ai"

    def hydration_wait_selector(self) -> str | None:
        return "[data-hostai-loaded=\"true\"]"

    def hydration_extra_wait_ms(self) -> int:
        return 1500

    def extract(self, html: str, url: str) -> ExtractionResult:
        soup = BeautifulSoup(html, "lxml")
        result = ExtractionResult()

        if (html_tag := soup.find("html")) and html_tag.get("lang"):
            result.page_lang = str(html_tag.get("lang"))
        if (title := soup.find("title")) and title.string:
            result.page_title = title.string.strip()

        # Buscar secciones marcadas. Soporta también legado Zyro (`data-zyro-block`).
        sections = soup.find_all(attrs={"data-block-type": True}) + soup.find_all(
            attrs={"data-zyro-block": True}
        )

        for idx, section in enumerate(sections):
            kind = section.get("data-block-type") or section.get("data-zyro-block")
            kind = (kind or "").lower()
            block_type = HOSTINGER_BLOCK_MAP.get(kind, BlockType.UNKNOWN)
            block = ExtractedBlock(
                block_type=block_type,
                order_index=idx,
                content_json=self._extract_content(section, block_type),
                lang=result.page_lang,
            )
            if block_type is BlockType.UNKNOWN:
                block.notes = f"Hostinger AI data-block-type='{kind}' no mapeado"
            result.blocks.append(block)

        # Theme hints en <html> style/css vars
        self._collect_theme_hints(html, result)
        result.asset_urls = self._extract_image_urls(soup)
        result.font_urls = self._extract_font_urls(html)
        result.video_urls = self._extract_video_urls(soup)

        return result

    # ---------- helpers ----------

    def _extract_content(self, section: Tag, block_type: BlockType) -> dict:
        if block_type is BlockType.HERO:
            return self._extract_hero(section)
        if block_type in {BlockType.HEADING, BlockType.TEXT}:
            return self._extract_text_or_heading(section, block_type)
        if block_type is BlockType.IMAGE:
            img = section.find("img")
            return {
                "src": img.get("src") if img else None,
                "alt": img.get("alt") if img else None,
            }
        if block_type is BlockType.GALLERY:
            return {
                "image_urls": [i.get("src") for i in section.find_all("img") if i.get("src")],
                "asset_ids": [],
                "layout": section.get("data-layout", "grid"),
            }
        if block_type is BlockType.CTA:
            link = section.find("a")
            return {
                "text": link.get_text(strip=True) if link else "",
                "url": link.get("href") if link else "#",
                "style": "primary",
            }
        if block_type is BlockType.FAQ:
            items = []
            for item in section.find_all(attrs={"data-role": "faq-item"}):
                q = item.find(attrs={"data-role": "question"})
                a = item.find(attrs={"data-role": "answer"})
                if q:
                    items.append({"q": q.get_text(strip=True), "a": a.get_text(strip=True) if a else ""})
            return {"items": items}
        if block_type is BlockType.PRICING:
            tiers = []
            for tier in section.find_all(attrs={"data-role": "pricing-tier"}):
                name = tier.find(attrs={"data-role": "tier-name"})
                price = tier.find(attrs={"data-role": "tier-price"})
                tiers.append(
                    {
                        "name": name.get_text(strip=True) if name else "",
                        "price": price.get_text(strip=True) if price else "",
                        "features": [
                            li.get_text(strip=True)
                            for li in tier.select('[data-role="tier-feature"]')
                        ],
                    }
                )
            return {"tiers": tiers}
        if block_type is BlockType.TESTIMONIAL:
            quote = section.find(attrs={"data-role": "quote"})
            author = section.find(attrs={"data-role": "author"})
            return {
                "quote": quote.get_text(strip=True) if quote else "",
                "author": author.get_text(strip=True) if author else "",
            }
        if block_type is BlockType.FORM:
            return {"fields": [], "notes": "Hostinger Form — recrear en Gravity Forms"}
        # default
        return {"raw_html": str(section)[:3000]}

    def _extract_hero(self, section: Tag) -> dict:
        headline = section.find(attrs={"data-role": "headline"}) or section.find("h1")
        subheadline = section.find(attrs={"data-role": "subheadline"})
        cta = section.find(attrs={"data-role": "cta"}) or section.find("a")
        bg_img = section.find(attrs={"data-role": "bg-image"})
        return {
            "headline": headline.get_text(strip=True) if headline else None,
            "subheadline": subheadline.get_text(strip=True) if subheadline else None,
            "cta_text": cta.get_text(strip=True) if cta else None,
            "cta_url": cta.get("href") if cta else None,
            "bg_image_url": bg_img.get("src") if bg_img else None,
        }

    def _extract_text_or_heading(self, section: Tag, block_type: BlockType) -> dict:
        if block_type is BlockType.HEADING:
            tag = section.find(re.compile(r"^h[1-6]$"))
            return {
                "level": tag.name if tag else "h2",
                "text": tag.get_text(strip=True) if tag else section.get_text(strip=True),
            }
        return {"html": str(section)[:10000]}

    def _collect_theme_hints(self, html: str, result: ExtractionResult) -> None:
        # CSS variables --hostai-* del <html>
        colors = re.findall(r'--hostai-(primary|secondary|accent):\s*([^;]+);', html)
        if colors:
            result.notes.append(
                "Theme colors detectados: "
                + ", ".join(f"{k}={v.strip()}" for k, v in colors)
            )
        fonts = re.findall(r'--hostai-font-(heading|body):\s*([^;]+);', html)
        if fonts:
            result.notes.append(
                "Theme fonts detectados: "
                + ", ".join(f"{k}={v.strip()}" for k, v in fonts)
            )

    def _extract_image_urls(self, soup: BeautifulSoup) -> list[str]:
        urls: set[str] = set()
        for img in soup.find_all("img"):
            if src := img.get("src"):
                urls.add(src)
        return sorted(u for u in urls if u.startswith(("http", "//")))

    def _extract_font_urls(self, html: str) -> list[str]:
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
