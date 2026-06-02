"""Tests del BricksAdaptAgent (v0.28.0 B5)."""

from __future__ import annotations

from unittest.mock import MagicMock

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.bricks_adapt import BricksAdaptAgent


def _make_ctx(pages_data: list[tuple[str, list[dict]]], assets_data: list = None):
    """Construye un AgentContext con session mock que devuelve las pages
    indicadas en el primer execute().scalars().all() y assets en el segundo."""
    session = MagicMock()
    pages = []
    for slug, json_content in pages_data:
        bp = MagicMock()
        bp.slug = slug
        bp.bricks_json = json_content
        bp.project_id = 42
        pages.append(bp)
    assets = assets_data or []
    # execute() devuelve un MagicMock cuyo .scalars().all() cicla por las
    # listas en orden de invocación.
    call_results = [pages, assets]
    call_idx = [0]

    def fake_execute(_stmt):
        idx = call_idx[0]
        call_idx[0] += 1
        result = MagicMock()
        result.scalars.return_value.all.return_value = call_results[idx]
        return result

    session.execute.side_effect = fake_execute
    return AgentContext(session=session, project_id=42)


def test_agent_skipped_without_project_id() -> None:
    ctx = AgentContext(session=MagicMock(), project_id=None)
    result = BricksAdaptAgent().run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_project_id"


def test_agent_skipped_without_pages() -> None:
    ctx = _make_ctx(pages_data=[])
    result = BricksAdaptAgent().run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_pages"


def test_agent_fixes_typography_underscore_in_pages() -> None:
    """Caso E2E v0.27.0 — la página viene con font_size (underscore)."""
    buggy = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["hed001"], "settings": {}},
        {"id": "hed001", "name": "heading", "parent": "sec001", "children": [],
         "settings": {
             "text": "Hello",
             "tag": "h1",
             "_typography": {"font_size": "2rem", "font_family": "Inter"},
         }},
    ]
    ctx = _make_ctx(pages_data=[("home", buggy)])
    result = BricksAdaptAgent().run(ctx)
    assert result.outputs["pages_modified"] == 1
    assert result.outputs["pages_total"] == 1
    assert result.outputs["fixes_total"] >= 2  # font_size + font_family
    assert result.outputs["fixes_breakdown"]["typography_keys_fixed"] == 2


def test_agent_idempotent_when_pages_already_correct() -> None:
    """Páginas con shape correcto no se modifican."""
    correct = [
        {"id": "sec001", "name": "section", "parent": "0", "children": ["hed001"], "settings": {}},
        {"id": "hed001", "name": "heading", "parent": "sec001", "children": [],
         "settings": {
             "text": "Hello",
             "tag": "h1",
             "_typography": {"font-size": "2rem", "font-family": "Inter"},
         }},
    ]
    ctx = _make_ctx(pages_data=[("home", correct)])
    result = BricksAdaptAgent().run(ctx)
    assert result.outputs["pages_modified"] == 0
    assert result.outputs["fixes_total"] == 0


def test_build_wp_asset_map_maps_both_urls() -> None:
    """El mapa debe contener both `original_url` y `wp_source_url` apuntando
    al mismo wp_data."""
    asset = MagicMock()
    asset.wp_attachment_id = 999
    asset.original_url = "https://wix.com/hero.jpg"
    asset.wp_source_url = "https://wp.example.com/hero.jpg"

    session = MagicMock()
    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = [asset]
    session.execute.return_value = result_obj
    ctx = AgentContext(session=session, project_id=42)
    mapping = BricksAdaptAgent._build_wp_asset_map(ctx)
    assert "https://wix.com/hero.jpg" in mapping
    assert "https://wp.example.com/hero.jpg" in mapping
    assert mapping["https://wix.com/hero.jpg"]["id"] == 999
    assert mapping["https://wp.example.com/hero.jpg"]["id"] == 999


def test_build_wp_asset_map_handles_missing_wp_source_url() -> None:
    """Asset con wp_attachment_id pero sin wp_source_url se mapea solo
    por original_url."""
    asset = MagicMock()
    asset.wp_attachment_id = 1
    asset.original_url = "https://wix.com/a.jpg"
    asset.wp_source_url = None

    session = MagicMock()
    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = [asset]
    session.execute.return_value = result_obj
    ctx = AgentContext(session=session, project_id=42)
    mapping = BricksAdaptAgent._build_wp_asset_map(ctx)
    assert mapping == {"https://wix.com/a.jpg": {
        "id": 1,
        "filename": "a.jpg",
        "size": "large",
        "url": "https://wix.com/a.jpg",
        "full": "https://wix.com/a.jpg",
    }}
