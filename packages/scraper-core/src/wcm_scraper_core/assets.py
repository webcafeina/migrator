"""Asset discovery — enumera URLs de imágenes, fonts y vídeos en un HTML.

Output: `AssetRef` con URL absoluta, tipo, y hints (alt, dimensiones, srcset).
La descarga + optimización es responsabilidad de `asset-optimizer` agente
(skill `image-pipeline`); aquí solo enumeramos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

AssetType = Literal["image", "font", "video", "stylesheet", "script"]


@dataclass
class AssetRef:
    url: str
    asset_type: AssetType
    referenced_from: str = ""  # selector o atributo que originó la referencia
    alt: str | None = None
    width: int | None = None
    height: int | None = None
    srcset: str | None = None
    is_external: bool = False  # dominio distinto al base


@dataclass
class AssetDiscoveryResult:
    images: list[AssetRef] = field(default_factory=list)
    fonts: list[AssetRef] = field(default_factory=list)
    videos: list[AssetRef] = field(default_factory=list)
    stylesheets: list[AssetRef] = field(default_factory=list)
    scripts: list[AssetRef] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _absolute(base_url: str, url: str) -> str:
    if url.startswith("//"):
        return ("https:" + url) if base_url.startswith("https") else ("http:" + url)
    return urljoin(base_url, url)


def _is_external(asset_url: str, base_url: str) -> bool:
    a, b = urlparse(asset_url).hostname, urlparse(base_url).hostname
    if not a or not b:
        return False
    return a != b


def discover_assets(html: str, base_url: str) -> AssetDiscoveryResult:
    """Recorre el HTML y agrupa todas las referencias a assets externos.

    Resolución de URLs:
    - Absolutas (`https://...`) → tal cual.
    - Protocol-relative (`//cdn.../`) → completar con scheme del base.
    - Relativas (`/img/`, `img.png`) → `urljoin(base, relativa)`.
    """
    soup = BeautifulSoup(html, "lxml")
    result = AssetDiscoveryResult()

    # ---------- imágenes ----------
    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            if val := img.get(attr):
                abs_url = _absolute(base_url, val)
                width_attr = img.get("width")
                height_attr = img.get("height")
                width = (
                    int(width_attr)
                    if width_attr and width_attr.isdigit()
                    else None
                )
                height = (
                    int(height_attr)
                    if height_attr and height_attr.isdigit()
                    else None
                )
                result.images.append(
                    AssetRef(
                        url=abs_url,
                        asset_type="image",
                        referenced_from=f"img[{attr}]",
                        alt=img.get("alt"),
                        width=width,
                        height=height,
                        srcset=img.get("srcset"),
                        is_external=_is_external(abs_url, base_url),
                    )
                )
        if srcset := img.get("srcset"):
            for entry in srcset.split(","):
                candidate = entry.strip().split(" ", 1)[0]
                if not candidate:
                    continue
                abs_url = _absolute(base_url, candidate)
                result.images.append(
                    AssetRef(
                        url=abs_url,
                        asset_type="image",
                        referenced_from="img[srcset]",
                        is_external=_is_external(abs_url, base_url),
                    )
                )

    # background-image en estilos inline + clases
    for css_match in re.finditer(r'background[^:]*:\s*[^;}]*url\(["\']?([^"\')]+)["\']?\)', html):
        url = css_match.group(1)
        abs_url = _absolute(base_url, url)
        result.images.append(
            AssetRef(
                url=abs_url,
                asset_type="image",
                referenced_from="css:background-image",
                is_external=_is_external(abs_url, base_url),
            )
        )

    # picture > source
    for source in soup.select("picture source[srcset]"):
        for entry in source.get("srcset", "").split(","):
            candidate = entry.strip().split(" ", 1)[0]
            if candidate:
                abs_url = _absolute(base_url, candidate)
                result.images.append(
                    AssetRef(
                        url=abs_url,
                        asset_type="image",
                        referenced_from="picture>source[srcset]",
                        is_external=_is_external(abs_url, base_url),
                    )
                )

    # ---------- fonts ----------
    for font_match in re.finditer(
        r'@font-face\s*\{[^}]*src:\s*[^}]*url\(["\']?([^"\')]+)["\']?\)',
        html,
        re.S,
    ):
        url = font_match.group(1)
        abs_url = _absolute(base_url, url)
        result.fonts.append(
            AssetRef(
                url=abs_url,
                asset_type="font",
                referenced_from="@font-face",
                is_external=_is_external(abs_url, base_url),
            )
        )
    # Google Fonts <link>
    for link in soup.find_all("link", href=re.compile(r"fonts\.googleapis\.com")):
        result.fonts.append(
            AssetRef(
                url=link.get("href", ""),
                asset_type="font",
                referenced_from="link[href*=fonts.googleapis]",
                is_external=True,
            )
        )
        result.notes.append("Google Fonts detectado — preservar referencia, no descargar")

    # ---------- videos ----------
    for v in soup.find_all("video"):
        if src := v.get("src"):
            abs_url = _absolute(base_url, src)
            result.videos.append(
                AssetRef(
                    url=abs_url,
                    asset_type="video",
                    referenced_from="video[src]",
                    is_external=_is_external(abs_url, base_url),
                )
            )
        for source in v.find_all("source"):
            if src := source.get("src"):
                abs_url = _absolute(base_url, src)
                result.videos.append(
                    AssetRef(
                        url=abs_url,
                        asset_type="video",
                        referenced_from="video>source[src]",
                        is_external=_is_external(abs_url, base_url),
                    )
                )
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if "youtube" in src or "vimeo" in src or "loom" in src:
            result.videos.append(
                AssetRef(
                    url=src,
                    asset_type="video",
                    referenced_from="iframe[src]",
                    is_external=True,
                )
            )

    # ---------- stylesheets + scripts ----------
    for link in soup.find_all("link", rel=lambda v: v and "stylesheet" in v):
        if href := link.get("href"):
            abs_url = _absolute(base_url, href)
            result.stylesheets.append(
                AssetRef(
                    url=abs_url,
                    asset_type="stylesheet",
                    referenced_from="link[rel=stylesheet]",
                    is_external=_is_external(abs_url, base_url),
                )
            )

    for script in soup.find_all("script", src=True):
        if src := script.get("src"):
            abs_url = _absolute(base_url, src)
            result.scripts.append(
                AssetRef(
                    url=abs_url,
                    asset_type="script",
                    referenced_from="script[src]",
                    is_external=_is_external(abs_url, base_url),
                )
            )

    # Deduplicar por URL preservando orden
    for bucket_name in ("images", "fonts", "videos", "stylesheets", "scripts"):
        bucket: list[AssetRef] = getattr(result, bucket_name)
        seen: set[str] = set()
        dedup: list[AssetRef] = []
        for a in bucket:
            if a.url and a.url not in seen:
                seen.add(a.url)
                dedup.append(a)
        setattr(result, bucket_name, dedup)

    return result
