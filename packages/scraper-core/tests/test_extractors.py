"""Tests de los extractors por builder contra fixtures HTML."""

from __future__ import annotations

from wcm_types.enums import BlockType, BuilderType

from wcm_scraper_core.extractors import (
    HostingerExtractor,
    WebflowExtractor,
    WixExtractor,
    get_extractor,
)


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
