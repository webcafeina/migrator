"""Tests del asset discovery."""

from __future__ import annotations

from wcm_scraper_core.assets import discover_assets


def test_discover_images_from_img_tags(wix_corporate_html: str) -> None:
    result = discover_assets(wix_corporate_html, "https://laencina.wixsite.com/")
    assert len(result.images) == 3
    for img in result.images:
        assert img.asset_type == "image"
        assert img.url.startswith("https://static.wixstatic.com/")


def test_discover_image_alts_preserved(wix_corporate_html: str) -> None:
    result = discover_assets(wix_corporate_html, "https://laencina.wixsite.com/")
    alts = {img.alt for img in result.images if img.alt}
    assert "Migas extremeñas" in alts


def test_discover_external_flag(webflow_agency_html: str) -> None:
    result = discover_assets(webflow_agency_html, "https://pinestudio.webflow.io/")
    # Las imágenes vienen de uploads-ssl.webflow.com, distinto al base
    assert all(img.is_external for img in result.images)


def test_discover_scripts_and_stylesheets(webflow_agency_html: str) -> None:
    result = discover_assets(webflow_agency_html, "https://pinestudio.webflow.io/")
    assert any("css.css" in s.url for s in result.stylesheets)
    assert any("webflow.js" in s.url for s in result.scripts)


def test_relative_url_resolution() -> None:
    html = """
    <html><body>
      <img src="/uploads/foo.jpg" alt="Foo">
      <img src="//cdn.example.com/bar.jpg" alt="Bar">
      <img src="https://other.com/baz.jpg" alt="Baz">
    </body></html>
    """
    result = discover_assets(html, "https://site.example/")
    urls = [img.url for img in result.images]
    assert "https://site.example/uploads/foo.jpg" in urls
    assert "https://cdn.example.com/bar.jpg" in urls
    assert "https://other.com/baz.jpg" in urls


def test_google_fonts_detected_separately() -> None:
    html = """
    <html><head>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700" rel="stylesheet">
    </head></html>
    """
    result = discover_assets(html, "https://site.example/")
    assert any("googleapis" in f.url for f in result.fonts)
    assert any("Google Fonts" in n for n in result.notes)


def test_background_image_extracted_from_css() -> None:
    html = '''
    <html><body>
      <div style="background-image: url('/img/bg.jpg');"></div>
    </body></html>
    '''
    result = discover_assets(html, "https://site.example/")
    assert any("bg.jpg" in img.url for img in result.images)


def test_video_iframe_youtube() -> None:
    html = '<html><body><iframe src="https://www.youtube.com/embed/abc123"></iframe></body></html>'
    result = discover_assets(html, "https://site.example/")
    assert any("youtube" in v.url for v in result.videos)


def test_dedup_preserves_order() -> None:
    html = """
    <html><body>
      <img src="https://cdn/a.jpg">
      <img src="https://cdn/b.jpg">
      <img src="https://cdn/a.jpg">
    </body></html>
    """
    result = discover_assets(html, "https://site.example/")
    urls = [i.url for i in result.images]
    assert urls.count("https://cdn/a.jpg") == 1
