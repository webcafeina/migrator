"""Tests del CLI `wcm email-layout theme` (v0.15.0)."""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _layout(theme: dict | None) -> dict:
    return {
        "id": 1,
        "layout_html": "<html></html>",
        "layout_css": "",
        "theme_config": theme,
        "updated_by_user_id": None,
        "created_at": "2026-05-19T10:00:00Z",
        "updated_at": "2026-05-19T10:00:00Z",
    }


def test_theme_show_imprime_json_si_existe(runner: CliRunner, authenticated) -> None:
    theme = {"cta_bg": "#B1F100", "card_max_width_px": 600, "show_logo": True}
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(200, json=_layout(theme))
        result = runner.invoke(app, ["email-layout", "theme", "show"])
    assert result.exit_code == 0, result.output
    assert "#B1F100" in result.output
    assert "card_max_width_px" in result.output


def test_theme_show_avisa_si_null(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(200, json=_layout(None))
        result = runner.invoke(app, ["email-layout", "theme", "show"])
    assert result.exit_code == 0
    assert "NULL" in result.output
    assert "reset" in result.output.lower()


def test_theme_reset_sin_confirm_falla(runner: CliRunner, authenticated) -> None:
    result = runner.invoke(app, ["email-layout", "theme", "reset"])
    assert result.exit_code != 0
    assert "--confirm" in result.output


def test_theme_reset_con_confirm_put_default(runner: CliRunner, authenticated) -> None:
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json=_layout({"cta_bg": "#B1F100"}))

    with respx.mock(base_url="http://api.test") as router:
        router.put("/api/v1/email-layout").mock(side_effect=_capture)
        result = runner.invoke(app, ["email-layout", "theme", "reset", "--confirm"])
    assert result.exit_code == 0, result.output
    assert captured["body"]["theme_config"]["cta_bg"] == "#B1F100"
    assert "restaurado" in result.output.lower()


def test_theme_set_con_flags_merge_con_existente(runner: CliRunner, authenticated) -> None:
    existing = {"cta_bg": "#000000", "card_max_width_px": 600, "show_logo": True}
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json=_layout(existing))

    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(
            200, json=_layout(existing)
        )
        router.put("/api/v1/email-layout").mock(side_effect=_capture)
        result = runner.invoke(
            app,
            ["email-layout", "theme", "set", "--cta-bg", "#FF00FF", "--font-family", "serif"],
        )
    assert result.exit_code == 0, result.output
    sent = captured["body"]["theme_config"]
    # Mergeó: cta_bg sobreescrito, card_max_width preservado.
    assert sent["cta_bg"] == "#FF00FF"
    assert sent["font_family"] == "serif"
    assert sent["card_max_width_px"] == 600


def test_theme_set_sin_flags_falla(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(200, json=_layout(None))
        result = runner.invoke(app, ["email-layout", "theme", "set"])
    assert result.exit_code != 0
    assert "ning" in result.output.lower()  # "ningún flag"


def test_theme_set_sin_tema_previo_parte_de_defaults(runner: CliRunner, authenticated) -> None:
    """Si theme_config era NULL, partir de defaults Webcafeína + aplicar."""
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json=_layout({"cta_bg": "#FF0000"}))

    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(200, json=_layout(None))
        router.put("/api/v1/email-layout").mock(side_effect=_capture)
        result = runner.invoke(app, ["email-layout", "theme", "set", "--cta-bg", "#FF0000"])
    assert result.exit_code == 0, result.output
    sent = captured["body"]["theme_config"]
    # Override aplicado.
    assert sent["cta_bg"] == "#FF0000"
    # Default Webcafeína preservado para los no tocados.
    assert sent["card_max_width_px"] == 600
    assert sent["font_family"] == "system-ui"
