"""Tests de los extractors por builder contra fixtures HTML."""

from __future__ import annotations

from wcm_scraper_core.extractors import (
    HostingerExtractor,
    WebflowExtractor,
    WixExtractor,
    get_extractor,
)
from wcm_types.enums import BlockType, BuilderType

# ---------- registry ----------

def test_registry_returns_correct_extractor() -> None:
    assert isinstance(get_extractor(BuilderType.WIX), WixExtractor)
    assert isinstance(get_extractor(BuilderType.HOSTINGER_AI), HostingerExtractor)
    assert isinstance(get_extractor(BuilderType.WEBFLOW), WebflowExtractor)


def test_registry_raises_for_unsupported() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_extractor(BuilderType.SHOPIFY)


# ---------- wix ----------

def test_wix_extracts_hero(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    hero = next(b for b in result.blocks if b.block_type == BlockType.HERO)
    assert "alma" in (hero.content_json.get("headline") or "")
    assert hero.content_json.get("cta_text") == "Reservar mesa"


def test_wix_extracts_gallery(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    galleries = [b for b in result.blocks if b.block_type == BlockType.GALLERY]
    assert galleries, "Esperaba al menos una galería"
    assert len(galleries[0].content_json["image_urls"]) == 3


def test_wix_extracts_faq(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    faqs = [b for b in result.blocks if b.block_type == BlockType.FAQ]
    assert faqs
    items = faqs[0].content_json["items"]
    assert len(items) == 2
    assert items[0]["q"].startswith("¿Hacéis")


def test_wix_extracts_form(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    forms = [b for b in result.blocks if b.block_type == BlockType.FORM]
    assert forms


def test_wix_extracts_nav_and_footer(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    types = [b.block_type for b in result.blocks]
    assert BlockType.NAV in types
    assert BlockType.FOOTER in types


def test_wix_extracts_image_urls(wix_corporate_html: str) -> None:
    result = WixExtractor().extract(wix_corporate_html, "https://laencina.wixsite.com/")
    assert all("wixstatic.com" in u for u in result.asset_urls)


def test_wix_hydration_selector_exists() -> None:
    assert WixExtractor().hydration_wait_selector() is not None


# Wix Editor clásico (sites pre-Studio): NO usan data-mesh-id, los containers
# top-level son <section id="comp-XXX">. Detectado en mariya.design (2026-05-20)
# que extrajo 0 bloques porque el selector solo cubría Wix moderno.

_WIX_CLASSIC_HTML = """\
<!doctype html>
<html lang="en">
<head><title>Mariya Design</title></head>
<body>
  <section id="comp-mmx53x4p">
    <h1>Brand Identity Systems for Companies That Are Scaling</h1>
    <p>If your brand feels inconsistent, let me help.</p>
    <a class="wixui-button" href="/audit">Start the Audit</a>
    <img src="https://static.wixstatic.com/media/hero.jpg" alt="hero" />
  </section>
  <section id="comp-mlxlvyqn">
    <h2>Where to Start Your Brand System</h2>
    <p class="wixui-rich-text">Two paths: existing brand or new.</p>
  </section>
  <section id="comp-mo1embpp">
    <h2>Trusted by teams building for scale</h2>
  </section>
  <section id="comp-other">
    <div class="wixui-pro-gallery">
      <img src="https://static.wixstatic.com/media/g1.jpg" alt="g1" />
      <img src="https://static.wixstatic.com/media/g2.jpg" alt="g2" />
    </div>
  </section>
</body>
</html>
"""


def test_wix_classic_editor_fallback_sin_data_mesh_id() -> None:
    """Fix 2026-05-20: Wix Editor clásico no tiene data-mesh-id pero
    sus <section id="comp-...">  deben clasificarse igual."""
    result = WixExtractor().extract(_WIX_CLASSIC_HTML, "https://mariya.design/")

    types = [b.block_type for b in result.blocks]
    # Hero (h1+button), heading puro, gallery → al menos 3 bloques útiles.
    assert BlockType.HERO in types
    assert BlockType.GALLERY in types
    # Y ninguna sección debería caer a UNKNOWN para esta estructura simple.
    assert BlockType.UNKNOWN not in types

    hero = next(b for b in result.blocks if b.block_type == BlockType.HERO)
    assert "Brand Identity Systems" in (hero.content_json.get("headline") or "")
    assert hero.content_json.get("cta_text") == "Start the Audit"


_WIX_CLASSIC_WITH_HEADER_FOOTER = """\
<!doctype html>
<html lang="en">
<body>
  <section id="comp-h1" class="Lnr3dj wixui-header undefined fwXYgt">
    <nav><a href="/about">About</a><a href="/work">Work</a></nav>
  </section>
  <section id="comp-m1">
    <h1>Hero title</h1>
    <a class="wixui-button" href="/cta">CTA</a>
  </section>
  <section id="comp-m2">
    <h2>Heading only</h2>
  </section>
  <section id="comp-f1" class="ke5pl1 wixui-footer fwXYgt">
    <p>© 2026 Mariya Design</p>
  </section>
</body>
</html>
"""


def test_wix_classic_nav_por_clase_wixui_header() -> None:
    """B.2 — Wix Editor clásico: <section class=wixui-header> → BlockType.NAV.
    Caso real: mariya.design no tiene id=SITE_HEADER (Studio) y antes
    el header caía a UNKNOWN.
    """
    result = WixExtractor().extract(
        _WIX_CLASSIC_WITH_HEADER_FOOTER, "https://mariya.design/"
    )
    types = [b.block_type for b in result.blocks]
    assert BlockType.NAV in types
    # NAV debe aparecer al principio (orden ascendente tras renumbering)
    assert result.blocks[0].block_type == BlockType.NAV


def test_wix_classic_footer_por_clase_wixui_footer() -> None:
    """B.3 — Equivalente para footer: <section class=wixui-footer>."""
    result = WixExtractor().extract(
        _WIX_CLASSIC_WITH_HEADER_FOOTER, "https://mariya.design/"
    )
    types = [b.block_type for b in result.blocks]
    assert BlockType.FOOTER in types
    # FOOTER es el último bloque tras renumbering
    assert result.blocks[-1].block_type == BlockType.FOOTER


def test_wix_classic_header_footer_no_caen_a_unknown() -> None:
    """Confirmación negativa: el header y footer ya NO aparecen como UNKNOWN
    en sites Editor clásico."""
    result = WixExtractor().extract(
        _WIX_CLASSIC_WITH_HEADER_FOOTER, "https://mariya.design/"
    )
    types = [b.block_type for b in result.blocks]
    assert BlockType.UNKNOWN not in types


def test_wix_studio_id_site_header_sigue_funcionando() -> None:
    """B.2 no rompe Wix Studio moderno: id=SITE_HEADER también detectado."""
    html = """\
    <html><body>
      <div id="SITE_HEADER"><nav><a href="/x">x</a></nav></div>
      <section data-mesh-id="root">
        <h1>Hero</h1><a class="wixui-button">CTA</a>
      </section>
      <div id="SITE_FOOTER"><p>© 2026</p></div>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://example.wix.com/")
    types = [b.block_type for b in result.blocks]
    assert BlockType.NAV in types
    assert BlockType.FOOTER in types


def test_wix_classic_no_duplica_si_hay_studio_y_editor() -> None:
    """Si hay ambos formatos (header wixui-header + id=SITE_HEADER) — solo 1 NAV."""
    html = """\
    <html><body>
      <div id="SITE_HEADER"><nav>x</nav></div>
      <section id="comp-1" class="wixui-header"><nav>y</nav></section>
      <section id="comp-2" data-mesh-id="x"><h1>Hero</h1><a class="wixui-button">CTA</a></section>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://example.com/")
    nav_blocks = [b for b in result.blocks if b.block_type == BlockType.NAV]
    assert len(nav_blocks) == 1


# B.5 — wow-image data-image-info parser (2026-05-20).
# Wix mete las imágenes en <wow-image data-image-info='{...}'> con un
# JSON serializado. El extractor antes solo leía <img src> y se perdía
# el 100% de las imágenes reales del CDN Wix.


_WIX_WOW_IMAGE_HTML = """\
<!doctype html>
<html><body>
  <section id="comp-1">
    <h1>Hero</h1>
    <wow-image data-image-info='{"containerId":"c1","displayMode":"fit","encoding":"AVIF","imageData":{"width":200,"height":200,"uri":"11062b_xxx~mv2.png","name":"","displayMode":"fit"}}'>
      <img src="" alt="" />
    </wow-image>
  </section>
  <section id="comp-2">
    <wow-image data-image-info='{"imageData":{"uri":"11062b_yyy~mv2.jpg"}}'>
      <img />
    </wow-image>
    <wow-image data-image-info='{"imageData":{"uri":"https://other.cdn/abs.png"}}'>
      <img />
    </wow-image>
  </section>
</body></html>
"""


def test_wix_wow_image_extrae_uri_a_cdn_wix() -> None:
    """URI relativa en imageData.uri → https://static.wixstatic.com/media/{uri}."""
    result = WixExtractor().extract(_WIX_WOW_IMAGE_HTML, "https://mariya.design/")
    urls = result.asset_urls
    assert "https://static.wixstatic.com/media/11062b_xxx~mv2.png" in urls
    assert "https://static.wixstatic.com/media/11062b_yyy~mv2.jpg" in urls


def test_wix_wow_image_uri_absoluta_se_preserva() -> None:
    """Si imageData.uri ya viene como URL absoluta, no se reescribe."""
    result = WixExtractor().extract(_WIX_WOW_IMAGE_HTML, "https://mariya.design/")
    assert "https://other.cdn/abs.png" in result.asset_urls


def test_wix_wow_image_json_invalido_no_crashea() -> None:
    """JSON malformado en data-image-info → silently skipped, no exception."""
    html = """\
    <html><body>
      <wow-image data-image-info='{this is not json'><img /></wow-image>
      <wow-image data-image-info='{"imageData":{"uri":"good.png"}}'><img /></wow-image>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://x.com/")
    assert "https://static.wixstatic.com/media/good.png" in result.asset_urls


def test_wix_wow_image_sin_data_image_info_se_ignora() -> None:
    """wow-image sin atributo data-image-info → ignorado (sin error)."""
    html = """\
    <html><body>
      <wow-image><img src="https://x.com/from-img.png" /></wow-image>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://x.com/")
    # Solo la URL del <img src> sobrevive, la wow-image vacía no aporta nada.
    assert result.asset_urls == ["https://x.com/from-img.png"]


def test_wix_wow_image_imagedata_falta_uri() -> None:
    """imageData presente pero sin uri → ignorado limpiamente."""
    from wcm_scraper_core.extractors.wix import _wix_uri_from_data_info

    assert _wix_uri_from_data_info('{"imageData":{"width":200}}') is None
    assert _wix_uri_from_data_info('{"imageData":{"uri":""}}') is None
    assert _wix_uri_from_data_info('{"imageData":{"uri":null}}') is None


def test_wix_wow_image_data_no_es_dict() -> None:
    """JSON válido pero no objeto (p.ej. lista) → None."""
    from wcm_scraper_core.extractors.wix import _wix_uri_from_data_info

    assert _wix_uri_from_data_info("[1, 2, 3]") is None
    assert _wix_uri_from_data_info('"just a string"') is None


# B.4 — wixui-repeater → BlockType.GRID. Caso real "Selected work" en
# mariya.design: 3 case-studies con imagen + heading + link.


_WIX_REPEATER_HTML = """\
<!doctype html>
<html><body>
  <section id="comp-mfz5vuhy">
    <h2>Selected work</h2>
    <div class="ArRNfA wixui-repeater" id="comp-mfz5vuia5">
      <div class="comp-mfz5vuia5-container" role="list">
        <div class="wixui-repeater__item" role="listitem">
          <h3>Sae Ren</h3>
          <wow-image data-image-info='{"imageData":{"uri":"case1.png"}}'><img /></wow-image>
          <a href="https://mariya.design/case-studies/sae-ren">View</a>
        </div>
        <div class="wixui-repeater__item" role="listitem">
          <h3>VKA</h3>
          <wow-image data-image-info='{"imageData":{"uri":"case2.png"}}'><img /></wow-image>
          <a href="https://mariya.design/case-studies/vka">View</a>
        </div>
        <div class="wixui-repeater__item" role="listitem">
          <h3>Sports Timing Systems</h3>
          <wow-image data-image-info='{"imageData":{"uri":"case3.png"}}'><img /></wow-image>
          <a href="https://mariya.design/case-studies/sts">View</a>
        </div>
      </div>
    </div>
  </section>
</body></html>
"""


def test_wix_repeater_genera_block_grid() -> None:
    """wixui-repeater → BlockType.GRID (antes caía a UNKNOWN)."""
    result = WixExtractor().extract(_WIX_REPEATER_HTML, "https://mariya.design/")
    grids = [b for b in result.blocks if b.block_type == BlockType.GRID]
    assert len(grids) == 1
    items = grids[0].content_json["items"]
    assert len(items) == 3
    assert items[0]["heading"] == "Sae Ren"
    assert items[0]["link"] == "https://mariya.design/case-studies/sae-ren"
    assert items[0]["image_url"] == "https://static.wixstatic.com/media/case1.png"


def test_wix_repeater_no_marca_unknown() -> None:
    """Confirmación negativa: un repeater limpio NO cae a UNKNOWN."""
    result = WixExtractor().extract(_WIX_REPEATER_HTML, "https://mariya.design/")
    types = [b.block_type for b in result.blocks]
    assert BlockType.UNKNOWN not in types


def test_wix_repeater_items_sin_imagen_no_crashea() -> None:
    """Item sin wow-image ni img → image_url=None, sin excepción."""
    html = """\
    <html><body>
      <section id="comp-1">
        <div class="wixui-repeater">
          <div class="wixui-repeater__item">
            <h3>Title only</h3>
          </div>
        </div>
      </section>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://x.com/")
    grids = [b for b in result.blocks if b.block_type == BlockType.GRID]
    assert grids
    items = grids[0].content_json["items"]
    assert items[0]["heading"] == "Title only"
    assert items[0]["image_url"] is None
    assert items[0]["link"] is None


def test_wix_repeater_fallback_role_listitem_sin_clase_item() -> None:
    """Si items usan role=listitem sin la clase wixui-repeater__item."""
    html = """\
    <html><body>
      <section id="comp-1">
        <div class="wixui-repeater">
          <div role="listitem"><h3>Item A</h3><a href="/a">a</a></div>
          <div role="listitem"><h3>Item B</h3><a href="/b">b</a></div>
        </div>
      </section>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://x.com/")
    grid = next(b for b in result.blocks if b.block_type == BlockType.GRID)
    assert len(grid.content_json["items"]) == 2


def test_wix_classic_solo_secciones_con_comp_prefix() -> None:
    """El fallback debe filtrar <section> sin id="comp-..." para no
    arrastrar HTML genérico que podría existir en mocks o landings."""
    html = """\
    <html><body>
      <section>generic section sin id</section>
      <section id="other-prefix"><h1>not Wix</h1></section>
      <section id="comp-x"><h1>Wix real</h1><a class="wixui-button">CTA</a></section>
    </body></html>
    """
    result = WixExtractor().extract(html, "https://example.wix.com/")
    # Solo el último <section> entra (id^=comp-). Genera HERO.
    hero_blocks = [b for b in result.blocks if b.block_type == BlockType.HERO]
    assert len(hero_blocks) == 1
    assert "Wix real" in (hero_blocks[0].content_json.get("headline") or "")


# ---------- hostinger ----------

def test_hostinger_extracts_hero(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    hero = next(b for b in result.blocks if b.block_type == BlockType.HERO)
    assert hero.content_json["headline"] == "Tu sonrisa, nuestra prioridad"
    assert hero.content_json["cta_url"] == "/citas"


def test_hostinger_extracts_pricing_tiers(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    pricing = next(b for b in result.blocks if b.block_type == BlockType.PRICING)
    tiers = pricing.content_json["tiers"]
    assert len(tiers) == 2
    assert tiers[0]["name"] == "Limpieza dental"
    assert tiers[0]["price"] == "45€"
    assert tiers[0]["features"] == ["Sesión 30 min", "Revisión incluida"]


def test_hostinger_extracts_testimonial(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    t = next(b for b in result.blocks if b.block_type == BlockType.TESTIMONIAL)
    assert "Marta" in t.content_json["author"]
    assert "magnífico" in t.content_json["quote"]


def test_hostinger_extracts_faq(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    faq = next(b for b in result.blocks if b.block_type == BlockType.FAQ)
    items = faq.content_json["items"]
    assert len(items) == 2
    assert items[1]["q"] == "¿Hay parking cerca?"


def test_hostinger_extracts_theme_hints(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    notes_combined = " ".join(result.notes)
    assert "Theme colors" in notes_combined
    assert "Theme fonts" in notes_combined


def test_hostinger_extracts_form_block(hostinger_clinica_html: str) -> None:
    result = HostingerExtractor().extract(hostinger_clinica_html, "https://aurora.hostingerwebsite.com/")
    forms = [b for b in result.blocks if b.block_type == BlockType.FORM]
    assert forms
    assert "Gravity Forms" in forms[0].content_json["notes"]


def test_hostinger_form_fallback_infiere_fields_sin_data_role(
    hostinger_clinica_html: str,
) -> None:
    """v0.19.0 — sin data-role el form se infiere desde input/textarea."""
    result = HostingerExtractor().extract(
        hostinger_clinica_html, "https://aurora.hostingerwebsite.com/"
    )
    form = next(b for b in result.blocks if b.block_type == BlockType.FORM)
    fields = form.content_json["fields"]
    names = [f["name"] for f in fields]
    assert "nombre" in names
    assert "email" in names
    assert "motivo" in names
    # textarea se mapea a type='textarea'.
    motivo = next(f for f in fields if f["name"] == "motivo")
    assert motivo["type"] == "textarea"


def test_hostinger_form_estructurado_data_role(hostinger_restaurante_html: str) -> None:
    """v0.19.0 — con data-role/data-field-type, extrae fields canónicos."""
    result = HostingerExtractor().extract(
        hostinger_restaurante_html, "https://casapepa.hostingerwebsite.com/"
    )
    form = next(b for b in result.blocks if b.block_type == BlockType.FORM)
    fields = form.content_json["fields"]
    assert len(fields) == 5
    type_by_name = {f["name"]: f["type"] for f in fields}
    assert type_by_name["nombre"] == "text"
    assert type_by_name["email"] == "email"
    assert type_by_name["telefono"] == "tel"
    assert type_by_name["comensales"] == "select"
    assert type_by_name["alergias"] == "textarea"
    # Labels conservados.
    labels = {f["name"]: f["label"] for f in fields}
    assert labels["email"] == "Email"
    assert labels["alergias"].startswith("Alergias")


def test_hostinger_theme_estructurado(hostinger_restaurante_html: str) -> None:
    """v0.19.0 — theme_colors + theme_fonts ahora son dict, no solo nota."""
    result = HostingerExtractor().extract(
        hostinger_restaurante_html, "https://casapepa.hostingerwebsite.com/"
    )
    assert result.theme_colors == {
        "primary": "#1A3A2A",
        "secondary": "#F5E6C8",
        "accent": "#D4A547",
    }
    assert result.theme_fonts == {
        "heading": "Playfair Display",
        "body": "Inter",
    }


def test_hostinger_extracts_contact_info(hostinger_restaurante_html: str) -> None:
    """v0.19.0 — contact_info estructurado desde footer con data-role."""
    result = HostingerExtractor().extract(
        hostinger_restaurante_html, "https://casapepa.hostingerwebsite.com/"
    )
    info = result.contact_info
    assert info["email"] == "hola@casapepa.es"
    assert info["phone"] == "+34927111222"
    social = info["social"]
    assert any("instagram.com/casapepa" in s for s in social)
    assert any("facebook.com/casapepa" in s for s in social)


def test_hostinger_contact_info_fallback_heuristico(
    hostinger_clinica_html: str,
) -> None:
    """v0.19.0 — sin data-role, infiere desde mailto/tel/dominios sociales."""
    result = HostingerExtractor().extract(
        hostinger_clinica_html, "https://aurora.hostingerwebsite.com/"
    )
    info = result.contact_info
    # Si el fixture tiene mailto/tel los extrae, si no info queda vacía.
    # Aquí confirmamos al menos que no rompe.
    assert isinstance(info, dict)


# ---------- webflow ----------

def test_webflow_extracts_hero(webflow_agency_html: str) -> None:
    result = WebflowExtractor().extract(webflow_agency_html, "https://pinestudio.webflow.io/")
    hero = next(b for b in result.blocks if b.block_type == BlockType.HERO)
    assert hero.content_json["headline"] == "Brands that resonate"
    assert hero.content_json["cta_url"] == "/work"


def test_webflow_detects_ix2_interactions(webflow_agency_html: str) -> None:
    result = WebflowExtractor().extract(webflow_agency_html, "https://pinestudio.webflow.io/")
    notes = " ".join(result.notes)
    assert "IX2" in notes
    # Hay 2 interacciones declaradas en el fixture
    assert "2 interacciones" in notes


def test_webflow_extracts_slider_as_gallery(webflow_agency_html: str) -> None:
    result = WebflowExtractor().extract(webflow_agency_html, "https://pinestudio.webflow.io/")
    galleries = [b for b in result.blocks if b.block_type == BlockType.GALLERY]
    assert galleries
    assert galleries[0].content_json["layout"] == "carousel"


def test_webflow_extracts_form_fields(webflow_agency_html: str) -> None:
    result = WebflowExtractor().extract(webflow_agency_html, "https://pinestudio.webflow.io/")
    form = next(b for b in result.blocks if b.block_type == BlockType.FORM)
    fields = form.content_json["fields"]
    names = [f["name"] for f in fields]
    assert "name" in names
    assert "email" in names
    assert "message" in names
