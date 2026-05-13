"""SeoPreserverAgent — extrae meta SEO de scraped_pages.

MVP: extrae title, meta description, OG tags, canonical, hreflang,
JSON-LD raw, robots meta. Los persiste en `bricks_pages.seo_meta` cuando
estén disponibles los bricks_pages, o como warnings en el agent result.

En esta fase NO se generan redirects 301 (eso requiere conocer las URLs
destino, lo hace wp-deployer). NO se aplica plan de mejoras SEO (Fase 14).
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ScrapeStatus

from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import SeoPreserverError


class SeoPreserverAgent(BaseAgent):
    name = "seo-preserver"
    phase_name = "preserve_seo"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise SeoPreserverError("SeoPreserverAgent requiere project_id")

        stmt = select(ScrapedPage).where(
            ScrapedPage.project_id == ctx.project_id,
            ScrapedPage.status == ScrapeStatus.SUCCESS,
        )
        pages = ctx.session.execute(stmt).scalars().all()

        seo_by_slug: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []

        for page in pages:
            if not page.html_clean:
                continue
            seo = self._extract_seo(page.html_clean)
            slug = page.slug or "unknown"
            seo_by_slug[slug] = seo
            if not seo.get("title"):
                warnings.append(f"{page.url}: <title> vacío")
            if not seo.get("description"):
                warnings.append(f"{page.url}: meta description vacía")
            if seo.get("h1_count", 0) > 1:
                warnings.append(f"{page.url}: múltiples h1 ({seo['h1_count']})")

        # Persistir en project.theme_styles_origin como hint extra,
        # accesible por seo router del API en Fase 11.
        # En MVP los anotamos como output para el orchestrator.

        return AgentResult(
            summary=f"SEO extraído de {len(seo_by_slug)} páginas, {len(warnings)} avisos",
            outputs={
                "pages_audited": len(seo_by_slug),
                "warnings_count": len(warnings),
                "seo_by_slug": seo_by_slug,
            },
            warnings=warnings[:50],
        )

    @staticmethod
    def _extract_seo(html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.find("title")
        title = title_tag.string.strip() if title_tag and title_tag.string else None

        meta_desc = _get_meta(soup, "description")
        canonical = _get_link(soup, "canonical")
        robots = _get_meta(soup, "robots")

        og: dict[str, str] = {}
        twitter: dict[str, str] = {}
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") or meta.get("name", "")
            content = meta.get("content")
            if not content:
                continue
            if prop.startswith("og:"):
                og[prop[3:]] = content
            elif prop.startswith("twitter:"):
                twitter[prop[8:]] = content

        hreflang = []
        for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
            lang = link.get("hreflang")
            href = link.get("href")
            if lang and href:
                hreflang.append({"lang": lang, "url": href})

        json_ld = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                json_ld.append(json.loads(script.string or "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

        return {
            "title": title,
            "title_len": len(title) if title else 0,
            "description": meta_desc,
            "description_len": len(meta_desc) if meta_desc else 0,
            "canonical": canonical,
            "robots": robots,
            "og": og,
            "twitter": twitter,
            "hreflang": hreflang,
            "json_ld_count": len(json_ld),
            "h1_count": len(soup.find_all("h1")),
        }


def _get_meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return tag.get("content")
    return None


def _get_link(soup: BeautifulSoup, rel: str) -> str | None:
    tag = soup.find("link", attrs={"rel": rel})
    if tag and tag.get("href"):
        return tag.get("href")
    return None
