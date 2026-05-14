"""Tests del fingerprinter contra fixtures HTML."""

from __future__ import annotations

from wcm_scraper_core.fingerprint import fingerprint_url


def test_wix_detected_with_high_confidence(wix_corporate_html: str) -> None:
    result = fingerprint_url(
        html=wix_corporate_html,
        headers={"x-wix-request-id": "abc-123", "server": "Pepyaka/1.0"},
    )
    best = result.best_builder()
    assert best is not None
    assert best.name == "Wix"
    assert best.confidence >= 0.7


def test_hostinger_detected_with_high_confidence(hostinger_clinica_html: str) -> None:
    result = fingerprint_url(
        html=hostinger_clinica_html,
        headers={"server": "hostinger-cdn"},
    )
    best = result.best_builder()
    assert best is not None
    assert best.name == "Hostinger AI Builder"
    assert best.confidence >= 0.5


def test_webflow_detected_with_high_confidence(webflow_agency_html: str) -> None:
    result = fingerprint_url(
        html=webflow_agency_html,
        headers={"server": "Webflow"},
    )
    best = result.best_builder()
    assert best is not None
    assert best.name == "Webflow"
    assert best.confidence >= 0.7


def test_generic_html_returns_no_builder() -> None:
    result = fingerprint_url(html="<html><body><h1>Hola</h1></body></html>", headers={})
    assert result.best_builder() is None


def test_wordpress_detected_alongside_bricks() -> None:
    html = """
    <html>
    <head><meta name="generator" content="WordPress 6.5"></head>
    <body>
      <div class="brxe-abc123 bricks-is-frontend">
        <link href="/wp-content/themes/bricks/style.css" rel="stylesheet">
      </div>
    </body>
    </html>
    """
    result = fingerprint_url(html=html, headers={})
    names = [m.name for m in result.matches]
    assert "WordPress" in names
    assert "Bricks Builder" in names
    # cms gana sobre builder cuando coexisten
    best = result.best_builder()
    assert best is not None
    assert best.name == "WordPress"


def test_best_builder_prefers_wordpress_over_elementor() -> None:
    """Caso real: WP+Elementor (aolcomunicacion.com). Antes devolvía
    Elementor → OTHER. Ahora WordPress gana porque cms > builder."""
    html = """
    <html>
    <head><meta name="generator" content="WordPress 6.5"></head>
    <body>
      <link rel="stylesheet" href="/wp-content/themes/foo/style.css">
      <script src="/wp-includes/js/jquery.js"></script>
      <div class="elementor-page elementor-section">contenido</div>
    </body>
    </html>
    """
    result = fingerprint_url(html=html, headers={})
    names = [m.name for m in result.matches]
    assert "WordPress" in names
    assert "Elementor" in names
    best = result.best_builder()
    assert best is not None
    assert best.name == "WordPress", f"esperado WordPress, fue {best.name}"


def test_js_globals_optional() -> None:
    # Sin js_globals, los signals de tipo js_global se ignoran
    minimal_html = '<html><head></head><body><div data-w-id="x"></div></body></html>'
    result = fingerprint_url(html=minimal_html, headers={})
    # Webflow tiene `data-w-id` (peso 0.3) — debe llegar al umbral 0.3
    names = [m.name for m in result.matches]
    assert "Webflow" in names


def test_meta_generator_match() -> None:
    html = '<html><head><meta name="generator" content="WordPress 6.5"></head><body></body></html>'
    result = fingerprint_url(html=html, headers={})
    assert any(m.name == "WordPress" for m in result.matches)
