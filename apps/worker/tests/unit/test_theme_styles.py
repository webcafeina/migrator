"""Tests C.3 (2026-05-21) — ThemeStylesAgent.

Cubre:
- síntesis pura desde computed styles
- normalización de colores (rgb, rgba, transparent, #hex)
- typography keys filtradas
- agent.run: home sin scraped_pages, sin dom_tree_json, happy path
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.theme_styles import (
    DEFAULT_ACCENT,
    DEFAULT_BG,
    DEFAULT_PRIMARY,
    DEFAULT_TEXT,
    ThemeStylesAgent,
    _color_or_default,
    _typography_dict,
    synthesize_theme,
)
from wcm_worker.errors import ThemeStylesError

# ---------- _color_or_default ----------


@pytest.mark.parametrize(
    "css,expected",
    [
        ("rgb(255, 0, 0)", "#ff0000"),
        ("rgb(0, 0, 0)", "#000000"),
        ("rgb(177, 241, 0)", "#b1f100"),  # Lima Webcafeína
        ("rgba(0, 0, 0, 1)", "#000000"),
        ("rgba(255, 255, 255, 0.5)", "#ffffff"),
        ("RGB(10, 20, 30)", "#0a141e"),  # case-insensitive
        ("#abcdef", "#abcdef"),
        # Casos que caen al default
        ("rgba(0, 0, 0, 0)", "DEFAULT"),  # transparente
        ("transparent", "DEFAULT"),
        ("none", "DEFAULT"),
        ("", "DEFAULT"),
        (None, "DEFAULT"),
        ("not-a-color", "DEFAULT"),
    ],
)
def test_color_or_default(css: str | None, expected: str) -> None:
    result = _color_or_default(css, "#bada55")
    if expected == "DEFAULT":
        assert result == "#bada55"
    else:
        assert result == expected


# ---------- _typography_dict ----------


def test_typography_dict_filtra_props_relevantes() -> None:
    props = {
        "font-family": "Inter, sans-serif",
        "font-size": "48px",
        "font-weight": "700",
        "line-height": "1.2",
        "text-align": "center",
        "color": "rgb(0,0,0)",  # NO entra (no es typo prop)
        "padding": "20px",       # NO entra
    }
    result = _typography_dict(props)
    assert result == {
        "font-family": "Inter, sans-serif",
        "font-size": "48px",
        "font-weight": "700",
        "line-height": "1.2",
        "text-align": "center",
    }


def test_typography_dict_vacio_omite_keys() -> None:
    assert _typography_dict({}) == {}
    assert _typography_dict({"color": "red"}) == {}


# ---------- synthesize_theme ----------


def test_synthesize_theme_happy_path() -> None:
    computed = {
        "body": {
            "background-color": "rgb(255, 255, 255)",
            "color": "rgb(20, 20, 20)",
            "font-family": "Inter, sans-serif",
            "font-size": "16px",
        },
        "h1": {
            "font-family": "Playfair Display",
            "font-size": "64px",
            "font-weight": "700",
        },
        "h2": {"font-size": "32px"},
        "button": {
            "background-color": "rgb(0, 0, 0)",
            "color": "rgb(255, 255, 255)",
            "font-family": "Inter",
            "font-size": "14px",
        },
        "a": {"color": "rgb(177, 241, 0)"},
    }
    theme = synthesize_theme(computed)

    assert theme["colors"]["bg"] == "#ffffff"
    assert theme["colors"]["text"] == "#141414"
    assert theme["colors"]["primary"] == "#000000"
    assert theme["colors"]["accent"] == "#b1f100"

    assert theme["typography"]["h1"]["font-family"] == "Playfair Display"
    assert theme["typography"]["h1"]["font-size"] == "64px"
    assert theme["typography"]["body"]["font-family"] == "Inter, sans-serif"
    assert theme["typography"]["button"]["font-size"] == "14px"

    assert theme["spacing"]["section_y"] == "80px"
    assert theme["spacing"]["container_y"] == "24px"


def test_synthesize_theme_button_fallback_a_wixui_button() -> None:
    """Si no hay <button> pero sí .wixui-button, se usa este."""
    computed = {
        "body": {"background-color": "rgb(0,0,0)", "color": "rgb(255,255,255)"},
        ".wixui-button": {"background-color": "rgb(177,241,0)"},
    }
    theme = synthesize_theme(computed)
    assert theme["colors"]["primary"] == "#b1f100"


def test_synthesize_theme_bg_transparente_cae_a_default() -> None:
    """body sin background visible → bg = DEFAULT_BG (#ffffff)."""
    computed = {"body": {"background-color": "rgba(0, 0, 0, 0)"}}
    theme = synthesize_theme(computed)
    assert theme["colors"]["bg"] == DEFAULT_BG


def test_synthesize_theme_computed_vacio_no_crashea() -> None:
    """Computed totalmente vacío → todos los defaults."""
    theme = synthesize_theme({})
    assert theme["colors"]["bg"] == DEFAULT_BG
    assert theme["colors"]["text"] == DEFAULT_TEXT
    assert theme["colors"]["primary"] == DEFAULT_PRIMARY
    assert theme["colors"]["accent"] == DEFAULT_ACCENT
    assert theme["typography"]["h1"] == {}
    assert theme["typography"]["body"] == {}


# ---------- ThemeStylesAgent.run ----------


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 42
    p.theme_styles_origin = None
    return p


def _scraped_page_mock(*, dom_tree_json=None) -> MagicMock:
    p = MagicMock()
    p.id = 100
    p.depth = 0
    p.dom_tree_json = dom_tree_json
    return p


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(ThemeStylesError, match="project_id"):
        ThemeStylesAgent().run(AgentContext(session=fake_session))


def test_agent_sin_scraped_pages_skipped(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    fake_session.execute.return_value = res

    result = ThemeStylesAgent().run(
        AgentContext(session=fake_session, project_id=42)
    )
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_scraped_pages"


def test_agent_sin_computed_styles_skipped(fake_session) -> None:
    """home existe pero dom_tree_json=None → SKIPPED con warning explícito."""
    fake_session.get.return_value = _project_mock()
    home = _scraped_page_mock(dom_tree_json=None)
    res = MagicMock()
    res.scalar_one_or_none.return_value = home
    fake_session.execute.return_value = res

    result = ThemeStylesAgent().run(
        AgentContext(session=fake_session, project_id=42)
    )
    assert result.outputs["skipped"] is True
    assert result.outputs["reason"] == "no_computed_styles"
    assert "dom_tree_json vacío" in result.warnings[0]


def test_agent_happy_path_persiste_theme_en_project(fake_session) -> None:
    project = _project_mock()
    fake_session.get.return_value = project
    home = _scraped_page_mock(
        dom_tree_json={
            "body": {"background-color": "rgb(10,10,10)", "color": "rgb(240,240,240)"},
            "h1": {"font-family": "Inter", "font-size": "48px"},
            "button": {"background-color": "rgb(177,241,0)"},
        }
    )
    res = MagicMock()
    res.scalar_one_or_none.return_value = home
    fake_session.execute.return_value = res

    result = ThemeStylesAgent().run(
        AgentContext(session=fake_session, project_id=42)
    )

    # Theme persistido en project
    assert project.theme_styles_origin is not None
    assert project.theme_styles_origin["colors"]["bg"] == "#0a0a0a"
    assert project.theme_styles_origin["colors"]["primary"] == "#b1f100"
    assert project.theme_styles_origin["typography"]["h1"]["font-family"] == "Inter"

    # Outputs informativos
    assert result.outputs["skipped"] is False
    assert "primary" in result.outputs["colors"]
    assert "h1" in result.outputs["typography_keys"]
