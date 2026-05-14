"""Extractor para webs Webflow.

A diferencia de Wix/Hostinger, Webflow se beneficia del sidecar Puppeteer
para resolver correctamente la inicialización de IX2 (Interactions 2.0).
Aquí el extractor trabaja sobre HTML ya hidratado (capturado por el
sidecar o por Playwright con espera adecuada).

En MVP NO migramos IX2 — cada interacción significativa genera tarea
residual.

Patrones documentados en `.claude/skills/webflow-extraction/SKILL.md`.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from wcm_scraper_core.extractors.base import ExtractedBlock, ExtractionResult
from wcm_types.enums import BlockType


class WebflowExtractor:
    builder_name = "webflow"

    def hydration_wait_selector(self) -> str | None:
        # Webflow declara data-wf-page en <html> — fiable como signal de carga
        return "html[data-wf-page]"

    def hydration_extra_wait_ms(self) -> int:
        return 1500

    def extract(self, html: str, url: str) -> ExtractionResult:
        soup = BeautifulSoup(html, "lxml")
        result = ExtractionResult()

        # Page meta
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            result.page_lang = str(html_tag.get("lang"))
        if (title := soup.find("title")) and title.string:
            result.page_title = title.string.strip()

        # Recolectar interacciones IX2 declaradas → tareas residuales
        ix2_count = self._count_ix2_interactions(html)
        if ix2_count > 0:
            result.notes.append(
                f"Detectadas {ix2_count} interacciones Webflow IX2 — generar "
                f"{ix2_count} tareas residuales para recrear animaciones"
            )

        # CMS Collections
        cms_lists = soup.find_all(attrs={"data-collection-list-id": True})
        for cms_list in cms_lists:
            result.notes.append(
                f"Detected Webflow CMS Collection list (data-collection-list-id="
                f"{cms_list.get('data-collection-list-id')}). En MVP se migra "
                "como posts/páginas WordPress estándar."
            )

        # Sections
        sections = soup.find_all("section") + soup.find_all(class_=re.compile(r"\bsection\b"))
        seen_ids: set[str] = set()
        order = 0
        for section in sections:
            sid = section.get("id") or str(id(section))
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            block = self._classify_section(section)
            if block is None:
                continue
            block.order_index = order
            block.lang = result.page_lang
            result.blocks.append(block)
            order += 1

        # Nav/footer
        if nav := soup.find("nav") or soup.find(class_=re.compile(r"\bw-nav\b")):
            result.blocks.insert(
                0,
                ExtractedBlock(
                    block_type=BlockType.NAV,
                    order_index=-1,
                    content_json={"raw_html": str(nav)[:5000]},
                    lang=result.page_lang,
                ),
            )
        if footer := soup.find("footer"):
            result.blocks.append(
                ExtractedBlock(
                    block_type=BlockType.FOOTER,
                    order_index=order,
                    content_json={"raw_html": str(footer)[:5000]},
                    lang=result.page_lang,
                )
            )
            order += 1

        # Renumerar
        result.blocks.sort(key=lambda b: b.order_index)
        for i, b in enumerate(result.blocks):
            b.order_index = i

        result.asset_urls = self._extract_image_urls(soup)
        result.font_urls = self._extract_font_urls(html)
        result.video_urls = self._extract_video_urls(soup)

        return result

    # ---------- helpers ----------

    def _count_ix2_interactions(self, html: str) -> int:
        # Webflow inyecta __WEBFLOW_CURRENCY_SETTINGS y/o un <script> ix2 con eventos.
        # Aproximación: contar data-w-id únicos referenciados en el script global.
        script = re.search(r"Webflow\.push\(function\(\)\s*\{(.+?)\}\);", html, re.S)
        if script is None:
            return 0
        return len(re.findall(r'"id"\s*:\s*"[a-f0-9-]+"', script.group(1)))

    def _classify_section(self, section: Tag) -> ExtractedBlock | None:
        has_h1 = section.find("h1") is not None
        has_button = bool(section.find(class_=re.compile(r"\bw-button\b")))
        has_image = bool(section.find("img"))
        has_form = bool(section.find("form")) or bool(section.find(class_=re.compile(r"\bw-form\b")))
        has_slider = bool(section.find(class_=re.compile(r"\bw-slider\b")))
        has_tabs = bool(section.find(class_=re.compile(r"\bw-tabs\b")))
        has_dropdown = bool(section.find(class_=re.compile(r"\bw-dropdown\b")))

        if has_form:
            return ExtractedBlock(
                block_type=BlockType.FORM,
                order_index=0,
                content_json={
                    "fields": self._extract_form_fields(section),
                    "notes": "Webflow Forms — recrear en Gravity Forms",
                },
            )

        if has_h1 and has_button:
            return ExtractedBlock(
                block_type=BlockType.HERO,
                order_index=0,
                content_json=self._extract_hero(section),
            )

        if has_slider:
            return ExtractedBlock(
                block_type=BlockType.GALLERY,
                order_index=0,
                content_json={
                    "image_urls": [
                        i.get("src") for i in section.find_all("img") if i.get("src")
                    ],
                    "layout": "carousel",
                    "asset_ids": [],
                },
            )

        if has_tabs or has_dropdown:
            return ExtractedBlock(
                block_type=BlockType.UNKNOWN,
                order_index=0,
                content_json={"raw_html": str(section)[:3000]},
                notes="Webflow tabs/dropdown — reconstruir con accordion o custom",
            )

        if section.find(["h2", "h3"]) and not has_image:
            h = section.find(["h2", "h3"])
            return ExtractedBlock(
                block_type=BlockType.HEADING,
                order_index=0,
                content_json={"level": h.name, "text": h.get_text(strip=True)},
            )

        if has_image and not has_button:
            img = section.find("img")
            return ExtractedBlock(
                block_type=BlockType.IMAGE,
                order_index=0,
                content_json={
                    "src": img.get("src") if img else None,
                    "alt": img.get("alt") if img else None,
                    "srcset": img.get("srcset") if img else None,
                },
            )

        # Texto puro
        text_nodes = section.find_all(["p", "div"], recursive=True)
        if text_nodes:
            txt = "\n".join(t.get_text(strip=True) for t in text_nodes[:5] if t.get_text(strip=True))
            if txt.strip():
                return ExtractedBlock(
                    block_type=BlockType.TEXT,
                    order_index=0,
                    content_json={"text": txt[:5000]},
                )

        return ExtractedBlock(
            block_type=BlockType.UNKNOWN,
            order_index=0,
            content_json={"raw_html": str(section)[:3000]},
            notes="Webflow section no clasificada en MVP",
        )

    def _extract_hero(self, section: Tag) -> dict:
        h1 = section.find("h1")
        sub = None
        for sib in (section.find_all(["p", "div"]) if h1 else []):
            txt = sib.get_text(strip=True)
            if txt and txt != h1.get_text(strip=True):
                sub = txt
                break
        button = section.find(class_=re.compile(r"\bw-button\b"))
        return {
            "headline": h1.get_text(strip=True) if h1 else None,
            "subheadline": sub,
            "cta_text": button.get_text(strip=True) if button else None,
            "cta_url": button.get("href") if button else None,
        }

    def _extract_form_fields(self, section: Tag) -> list[dict]:
        fields: list[dict] = []
        for inp in section.find_all("input"):
            field_type = inp.get("type", "text")
            fields.append(
                {
                    "type": field_type,
                    "name": inp.get("name", ""),
                    "required": inp.has_attr("required"),
                    "placeholder": inp.get("placeholder", ""),
                }
            )
        for ta in section.find_all("textarea"):
            fields.append(
                {
                    "type": "textarea",
                    "name": ta.get("name", ""),
                    "required": ta.has_attr("required"),
                }
            )
        return fields

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
            if "youtube" in src or "vimeo" in src or "loom" in src:
                urls.add(src)
        return sorted(urls)
