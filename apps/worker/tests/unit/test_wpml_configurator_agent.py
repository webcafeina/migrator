"""Tests del WpmlConfiguratorAgent (v0.17.0).

Decisión arquitectónica: Webcafeína NO tiene licencia WPML, por lo
que el agent SIEMPRE genera una ResidualTask manual (cuando
is_multilang=True) en lugar de configurar nada.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.wpml_configurator import (
    WpmlConfiguratorAgent,
    _build_residual_description,
    _estimate_minutes,
)
from wcm_worker.errors import WpmlConfiguratorError


def _project_mock(
    *,
    is_multilang: bool = True,
    langs: list[str] | None = None,
    primary_lang: str | None = "es",
) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.client_name = "Clínica Internacional"
    p.target_domain = "clinica.test"
    p.is_multilang = is_multilang
    p.langs = langs if langs is not None else ["es", "en"]
    p.primary_lang = primary_lang
    return p


def _page_mock(lang: str, slug: str) -> MagicMock:
    p = MagicMock()
    p.lang = lang
    p.slug = slug
    p.url = f"https://origen.test/{slug}"
    return p


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(WpmlConfiguratorError, match="project_id"):
        WpmlConfiguratorAgent().run(AgentContext(session=fake_session))


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(WpmlConfiguratorError, match="no encontrado"):
        WpmlConfiguratorAgent().run(
            AgentContext(session=fake_session, project_id=99)
        )


def test_is_multilang_false_salta_sin_residual(fake_session) -> None:
    fake_session.get.return_value = _project_mock(is_multilang=False)
    result = WpmlConfiguratorAgent().run(
        AgentContext(session=fake_session, project_id=7)
    )
    assert "saltada" in result.summary
    assert result.residual_tasks_created == 0
    fake_session.add.assert_not_called()


def test_happy_path_crea_residual_con_idiomas_y_paginas(fake_session) -> None:
    fake_session.get.return_value = _project_mock(
        langs=["es", "en", "fr"],
        primary_lang="es",
    )
    pages = [
        _page_mock("es", "inicio"),
        _page_mock("es", "contacto"),
        _page_mock("en", "home"),
        _page_mock("en", "contact"),
        _page_mock("fr", "accueil"),
    ]
    pages_result = MagicMock()
    pages_result.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = pages_result

    result = WpmlConfiguratorAgent().run(
        AgentContext(session=fake_session, project_id=7)
    )

    assert result.residual_tasks_created == 1
    assert result.outputs["langs"] == ["es", "en", "fr"]
    assert result.outputs["pages_total"] == 5
    assert result.outputs["pages_per_lang"]["en"] == 2

    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert len(residuals) == 1
    r = residuals[0]
    assert "WPML" in r.title
    assert "3 idiomas" in r.title
    assert "es" in r.description
    assert "en" in r.description
    assert "fr" in r.description
    assert "BLOCKING" in r.category.value.upper() or r.category.value == "blocking_go_live"


def test_estimate_minutes_escala_con_paginas() -> None:
    # 30 base + 5 por página secundaria
    pages_es = [MagicMock() for _ in range(5)]
    pages_en = [MagicMock() for _ in range(3)]
    pages_fr = [MagicMock() for _ in range(2)]
    by_lang = {"es": pages_es, "en": pages_en, "fr": pages_fr}
    # 30 + 5*(5+3+2) = 30 + 50 = 80
    assert _estimate_minutes(by_lang) == 80


def test_estimate_minutes_vacio_fallback() -> None:
    assert _estimate_minutes({}) == 60


def test_build_description_incluye_pasos_y_paginas() -> None:
    pages = {
        "es": [_page_mock("es", "contacto")],
        "en": [_page_mock("en", "contact")],
    }
    desc = _build_residual_description(
        client_name="Test SL",
        target_domain="test.es",
        langs=["es", "en"],
        primary="es",
        pages_by_lang=pages,
    )
    assert "NO tiene licencia WPML" in desc
    assert "Test SL" in desc
    assert "test.es" in desc
    assert "## Pasos" in desc
    assert "wpml.org" in desc
    assert "/contacto" in desc
    assert "/contact" in desc
