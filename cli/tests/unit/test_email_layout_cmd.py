"""Tests del CLI `wcm email-layout` (v0.14.0)."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _layout() -> dict:
    return {
        "id": 1,
        "layout_html": "<html><body>{{ content | safe }}</body></html>",
        "layout_css": "body { font-family: sans-serif; }",
        "updated_by_user_id": None,
        "created_at": "2026-05-18T10:00:00Z",
        "updated_at": "2026-05-18T10:00:00Z",
    }


def test_show_imprime_html_y_css(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(
            200, json=_layout()
        )
        result = runner.invoke(app, ["email-layout", "show"])
    assert result.exit_code == 0, result.output
    assert "layout_html" in result.output
    assert "layout_css" in result.output
    assert "font-family" in result.output


def test_show_html_file_vuelca_a_disco(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    out = tmp_path / "layout.html"
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(
            200, json=_layout()
        )
        result = runner.invoke(
            app, ["email-layout", "show", "--html-file", str(out)]
        )
    assert result.exit_code == 0
    assert out.exists()
    assert "{{ content | safe }}" in out.read_text()


def test_update_envia_put_con_html_y_css(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    html = tmp_path / "new.html"
    css = tmp_path / "new.css"
    html.write_text("<html><body>NUEVO {{ content | safe }}</body></html>")
    css.write_text(".x { color: red; }")

    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json=_layout())

    with respx.mock(base_url="http://api.test") as router:
        router.put("/api/v1/email-layout").mock(side_effect=_capture)
        result = runner.invoke(
            app,
            [
                "email-layout",
                "update",
                "--html",
                str(html),
                "--css",
                str(css),
            ],
        )
    assert result.exit_code == 0, result.output
    assert captured["body"]["layout_html"].startswith("<html>")
    assert "NUEVO" in captured["body"]["layout_html"]
    assert captured["body"]["layout_css"] == ".x { color: red; }"
    assert "actualizado" in result.output.lower()


def test_update_sin_css_conserva_actual(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    html = tmp_path / "new.html"
    html.write_text("<html><body>{{ content | safe }}</body></html>")

    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/email-layout").return_value = httpx.Response(
            200, json=_layout()
        )
        router.put("/api/v1/email-layout").return_value = httpx.Response(
            200, json=_layout()
        )
        result = runner.invoke(
            app, ["email-layout", "update", "--html", str(html)]
        )
    assert result.exit_code == 0, result.output


def test_update_html_inexistente_falla(runner: CliRunner, authenticated) -> None:
    result = runner.invoke(
        app, ["email-layout", "update", "--html", "/tmp/no-existe-12345.html"]
    )
    assert result.exit_code != 0
    assert "no encontrado" in result.output.lower()
