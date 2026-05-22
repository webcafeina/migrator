"""Tests del RedesignTemplatesAgent (Sprint v0.25.0 B5).

Mockea sesión SQLAlchemy + usa el mock catalog real del repo
(`docs/templates/brickstemplate-mock/`).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.redesign_templates import RedesignTemplatesAgent
from wcm_worker.errors import RedesignAgentError

MOCK_CATALOG = Path(__file__).resolve().parents[4] / "docs" / "templates" / "brickstemplate-mock"


def _project(
    *,
    id: int = 42,
    design_method: str | None = "templates",
    brief_json: dict | None = None,
    client_name: str = "Mariya Design",
    business_sector: str | None = "agency",
    tone_of_voice: str | None = "formal",
    primary_lang: str = "es",
) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.design_method = design_method
    p.brief_json = brief_json
    p.client_name = client_name
    p.business_sector = business_sector
    p.tone_of_voice = tone_of_voice
    p.primary_lang = primary_lang
    return p


def _ctx(fake_session: MagicMock, project: MagicMock) -> AgentContext:
    fake_session.get.return_value = project
    # bricks_page upsert lookup → None (no existe previo)
    fake_session.execute.return_value.scalar_one_or_none.return_value = None
    return AgentContext(session=fake_session, project_id=project.id)


# ---------- preconditions ----------


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(RedesignAgentError, match="project_id"):
        RedesignTemplatesAgent().run(AgentContext(session=fake_session))


def test_skipped_si_design_method_no_templates(fake_session) -> None:
    project = _project(design_method="ai")
    ctx = _ctx(fake_session, project)
    result = RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "design_method_mismatch"


def test_skipped_si_sin_brief_json(fake_session) -> None:
    project = _project(design_method="templates", brief_json=None)
    ctx = _ctx(fake_session, project)
    result = RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "no_brief"


def test_skipped_si_catalogo_vacio(fake_session, tmp_path: Path) -> None:
    """Catálogo inexistente (tmp_path) → SKIPPED + warning con instrucción."""
    project = _project(
        design_method="templates",
        brief_json={
            "business": {"name": "Acme", "sector": "agency", "tone_of_voice": "formal"},
            "pages": [{"slug": "home", "title": "Home", "sections": [{"type": "hero", "headline": "x"}]}],
        },
    )
    ctx = _ctx(fake_session, project)
    result = RedesignTemplatesAgent(catalog_dir=tmp_path).run(ctx)
    assert result.outputs.get("skipped") is True
    assert result.outputs.get("reason") == "empty_catalog"
    assert any("scripts/import_brickstemplate.py" in w for w in result.warnings)


# ---------- happy path con mock catalog ----------


def test_e2e_genera_brick_pages_con_mock_catalog(fake_session) -> None:
    """Brief con 1 página + 2 secciones (hero + cta) → genera 1 bricks_page
    con árbol concatenado de templates ensamblados."""
    project = _project(
        design_method="templates",
        business_sector="agency", tone_of_voice="formal",
        brief_json={
            "business": {"name": "Acme Agency", "sector": "agency", "tone_of_voice": "formal"},
            "pages": [
                {
                    "slug": "home",
                    "title": "Home",
                    "sections": [
                        {"type": "hero", "headline": "Diseño con propósito", "subheadline": "Identidades de marca", "cta": {"text": "Hablemos", "url": "/contacto"}},
                        {"type": "cta", "headline": "Empieza tu proyecto hoy", "cta": {"text": "Contáctanos", "url": "/contacto"}},
                    ],
                },
            ],
        },
    )
    ctx = _ctx(fake_session, project)

    # Capturar el bricks_page añadido al session.add.
    added = []
    fake_session.add.side_effect = lambda x: added.append(x)

    result = RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)

    assert result.outputs["skipped"] is False
    assert result.outputs["pages_generated"] == 1
    assert result.outputs["templates_used"] == 2
    assert result.outputs["sections_total"] == 2
    assert result.outputs["sections_unresolved"] == 0
    # Hubo 1 BricksPage añadida.
    bricks_pages_added = [x for x in added if type(x).__name__ == "BricksPage"]
    assert len(bricks_pages_added) == 1
    bp = bricks_pages_added[0]
    assert bp.slug == "home"
    # bricks_json contiene elementos de ambos templates ensamblados.
    json_str = str(bp.bricks_json)
    assert "Diseño con propósito" in json_str  # hero headline
    assert "Hablemos" in json_str  # hero CTA
    assert "Empieza tu proyecto hoy" in json_str  # cta headline


def test_e2e_residual_si_no_pickeable(fake_session) -> None:
    """Sección con tipo `pricing` no existe en mock → ResidualTask."""
    project = _project(
        design_method="templates",
        business_sector="agency", tone_of_voice="formal",
        brief_json={
            "business": {"name": "Acme", "sector": "agency", "tone_of_voice": "formal"},
            "pages": [
                {
                    "slug": "home",
                    "title": "Home",
                    "sections": [{"type": "pricing", "tiers": [{"name": "Basic", "price": "29€"}]}],
                },
            ],
        },
    )
    ctx = _ctx(fake_session, project)
    added = []
    fake_session.add.side_effect = lambda x: added.append(x)

    result = RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)

    assert result.outputs["sections_unresolved"] == 1
    assert result.outputs["templates_used"] == 0
    assert result.outputs["pages_generated"] == 0  # ningún template aplicado, página vacía
    residuals = [x for x in added if type(x).__name__ == "ResidualTask"]
    assert len(residuals) == 1
    assert "pricing" in residuals[0].title


# ---------- resolución de catalog ----------


def test_resolve_default_catalog_prefiere_prod_si_existe(tmp_path: Path, monkeypatch) -> None:
    """Si la prod path existe, se usa. Si no, fallback a mock."""
    # Crear stub prod dir
    monkeypatch.chdir(tmp_path)
    prod = tmp_path / "docs" / "templates" / "brickstemplate"
    prod.mkdir(parents=True)
    resolved = RedesignTemplatesAgent._resolve_default_catalog()
    # Debe haber elegido la prod existente.
    assert resolved.name == "brickstemplate"


def test_env_override_catalog_dir(monkeypatch, tmp_path: Path) -> None:
    """`WCM_TEMPLATES_CATALOG_DIR` env var override."""
    monkeypatch.setenv("WCM_TEMPLATES_CATALOG_DIR", str(tmp_path))
    agent = RedesignTemplatesAgent()
    assert agent.catalog_dir == tmp_path


# ---------- v0.26.0 — Hybrid mode (placeholders + marker) ----------


def test_corre_en_hybrid_design_method_none(fake_session) -> None:
    """v0.26.0 — Hybrid: design_method=None → corre (no skipped)."""
    brief = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [{
            "slug": "home", "title": "H", "intent": "landing",
            "sections": [{"type": "hero", "design_method": "templates",
                          "headline": "Hi"}],
        }],
    }
    project = _project(design_method=None, brief_json=brief)
    ctx = _ctx(fake_session, project)
    result = RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)
    assert result.outputs.get("skipped") is not True


def test_emite_placeholder_para_secciones_ai_en_hybrid(fake_session) -> None:
    """Hybrid: secciones con design_method=ai generan placeholder vacío
    con marker `_pending_ai=True`, no llaman al SectionPicker."""
    brief = {
        "business": {"name": "X", "sector": "agency", "tone_of_voice": "formal"},
        "brand": {"colors": {}, "fonts": {}},
        "pages": [{
            "slug": "home", "title": "H", "intent": "landing",
            "sections": [
                {"type": "hero", "design_method": "ai", "headline": "Hi"},
                {"type": "features", "design_method": "templates",
                 "items": [{"title": "F1", "description": "d1"}]},
            ],
        }],
    }
    project = _project(design_method=None, brief_json=brief)
    fake_session.get.return_value = project
    # Captura del add para inspeccionar lo upserted.
    added_pages: list[MagicMock] = []
    fake_session.add.side_effect = lambda obj: added_pages.append(obj)
    fake_session.execute.return_value.scalar_one_or_none.return_value = None
    ctx = AgentContext(session=fake_session, project_id=project.id)

    RedesignTemplatesAgent(catalog_dir=MOCK_CATALOG).run(ctx)

    # BricksPage debe haberse creado.
    bp = next(p for p in added_pages if hasattr(p, "bricks_json"))
    content = bp.bricks_json
    # El primer elemento es el placeholder de la sección AI.
    roots = [el for el in content if el.get("parent") == "0"]
    ai_root = roots[0]
    assert ai_root["settings"]["_pending_ai"] is True
    assert ai_root["settings"]["_brief_section_index"] == 0
    assert ai_root["settings"]["_brief_section_type"] == "hero"
    # El segundo root tiene el marker section_index=1.
    template_root = roots[1]
    assert template_root["settings"]["_brief_section_index"] == 1
    assert "_pending_ai" not in template_root["settings"]


def test_tag_root_section_helper() -> None:
    """Helper estático: añade _brief_section_index al primer root section."""
    content = [
        {"id": "sec000", "name": "section", "parent": "0", "settings": {}},
        {"id": "child0", "name": "text", "parent": "sec000", "settings": {}},
    ]
    RedesignTemplatesAgent._tag_root_section(content, section_index=5)
    assert content[0]["settings"]["_brief_section_index"] == 5
    # No toca a los descendientes.
    assert "_brief_section_index" not in content[1]["settings"]


def test_build_ai_placeholder_estructura() -> None:
    """Helper estático: placeholder es 1 section vacía con markers."""
    ph = RedesignTemplatesAgent._build_ai_placeholder(
        section_index=3, section_type="hero",
    )
    assert len(ph) == 1
    assert ph[0]["name"] == "section"
    assert ph[0]["parent"] == "0"
    assert ph[0]["settings"]["_pending_ai"] is True
    assert ph[0]["settings"]["_brief_section_index"] == 3
    assert ph[0]["settings"]["_brief_section_type"] == "hero"
