"""Tests del filtro `same-site` del BFS (bug 2026-05-20).

El sitio de origen puede declarar `source_url` sin `www.` (p.ej.
`https://mariya.design/`) pero servir todos los enlaces internos con
`www.` (`https://www.mariya.design/about`). El filtro original comparaba
`netloc == base_host` literalmente y rechazaba el 100% de internas. El
fix introduce `_same_site` que normaliza ambos lados quitando el prefix
`www.` antes de comparar.

Adicionalmente `_url_to_slug` debe tolerar que la URL descubierta tenga
host distinto al `source_url` (mismo sitio pero `www.` vs sin www).
"""

from __future__ import annotations

import pytest

from wcm_worker.agents.scraper_origin import ScraperOriginAgent


@pytest.mark.parametrize(
    "url,ref_host,expected",
    [
        # Idénticos
        ("https://mariya.design/about", "mariya.design", True),
        ("https://www.mariya.design/about", "www.mariya.design", True),
        # www. vs sin www. — bug 2026-05-20: era False, debe ser True
        ("https://www.mariya.design/about", "mariya.design", True),
        ("https://mariya.design/about", "www.mariya.design", True),
        # Mayúsculas — equivalentes
        ("https://Mariya.Design/about", "mariya.design", True),
        # Subdominio distinto != mismo sitio (privacy / seguridad)
        ("https://blog.mariya.design/post", "mariya.design", False),
        ("https://shop.mariya.design/x", "www.mariya.design", False),
        # Otro dominio
        ("https://example.com/", "mariya.design", False),
        ("https://www.wix.com/static.js", "www.mariya.design", False),
        # Path sin host (mailto/tel/javascript) → False seguro
        ("mailto:foo@bar.com", "mariya.design", False),
        ("javascript:void(0)", "mariya.design", False),
    ],
)
def test_same_site_tolera_www_y_subdominios(
    url: str, ref_host: str, expected: bool
) -> None:
    assert ScraperOriginAgent._same_site(url, ref_host) is expected


@pytest.mark.parametrize(
    "url,base_url,expected",
    [
        # Slug raíz → "home"
        ("https://mariya.design/", "https://mariya.design", "home"),
        ("https://mariya.design", "https://mariya.design", "home"),
        # Path simple
        ("https://mariya.design/about", "https://mariya.design", "about"),
        # base_url y url con `www.` divergentes — el bug original devolvía
        # la URL completa como slug (porque removeprefix no matcheaba).
        ("https://www.mariya.design/about", "https://mariya.design", "about"),
        ("https://mariya.design/about", "https://www.mariya.design", "about"),
        # Path multi-segmento: se conserva tal cual (con `/`)
        (
            "https://www.mariya.design/case-studies/sae-ren",
            "https://mariya.design",
            "case-studies/sae-ren",
        ),
        # Trailing slash irrelevante
        ("https://mariya.design/services/", "https://mariya.design", "services"),
    ],
)
def test_url_to_slug_usa_path_y_tolera_www(
    url: str, base_url: str, expected: bool
) -> None:
    assert ScraperOriginAgent._url_to_slug(url, base_url) == expected


def test_norm_host_minusculas_y_quita_www() -> None:
    assert ScraperOriginAgent._norm_host("WWW.Mariya.Design") == "mariya.design"
    assert ScraperOriginAgent._norm_host("mariya.design") == "mariya.design"
    assert ScraperOriginAgent._norm_host("www.foo.co.uk") == "foo.co.uk"
    # Sin prefix `www.` simplemente lowercases
    assert ScraperOriginAgent._norm_host("Foo.COM") == "foo.com"
