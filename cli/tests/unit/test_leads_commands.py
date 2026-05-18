"""Tests del comando `wcm leads create` (v0.11.0).

Cubre el patrón XOR --url/--bulk-file, parsing del fichero bulk,
respuesta exitosa, conflict 409 con `existing_lead_id`, y el resumen
del bulk con razones de fallo.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _ok_lead(lead_id: int, url: str = "https://barpepe.es") -> dict:
    return {
        "id": lead_id,
        "url": url,
        "business_name": None,
        "sector": None,
        "region": None,
        "country": "ES",
        "status": "discovered",
        "score": 0,
        "builder_detected": None,
        "builder_confidence": None,
        "builder_evidence": None,
        "emails": [],
        "phones": [],
        "social_links": {},
        "last_crawl_at": None,
        "embedding_model": None,
        "embedding_at": None,
        "created_at": "2026-05-18T12:00:00Z",
        "updated_at": "2026-05-18T12:00:00Z",
    }


def test_create_single_success(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads").return_value = httpx.Response(
            201, json=_ok_lead(lead_id=42, url="https://barpepe.es"),
        )
        result = runner.invoke(
            app, ["leads", "create", "--url", "https://barpepe.es"]
        )
    assert result.exit_code == 0, result.output
    assert "#42" in result.output
    assert "https://barpepe.es" in result.output


def test_create_single_409_shows_existing_id_and_exits_1(
    runner: CliRunner, authenticated
) -> None:
    """El 409 del API debe traducirse a mensaje específico mencionando
    el lead existente, no al genérico 'API HTTP 409'."""
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads").return_value = httpx.Response(
            409,
            json={
                "error": {
                    "code": "conflict",
                    "message": "Lead con esa URL ya existe",
                    "details": {"existing_lead_id": 13},
                }
            },
        )
        result = runner.invoke(
            app, ["leads", "create", "--url", "https://barpepe.es"]
        )
    assert result.exit_code == 1
    assert "URL duplicada" in result.output
    assert "#13" in result.output


def test_create_xor_validation_when_neither_provided(
    runner: CliRunner, authenticated
) -> None:
    """Sin --url ni --bulk-file → CliInputError."""
    result = runner.invoke(app, ["leads", "create"])
    assert result.exit_code != 0
    assert "xor" in result.output.lower() or "uno y solo uno" in result.output.lower()


def test_create_xor_validation_when_both_provided(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    """Con ambos --url Y --bulk-file → CliInputError."""
    f = tmp_path / "urls.txt"
    f.write_text("https://a.com\n")
    result = runner.invoke(
        app, ["leads", "create", "--url", "https://x.com", "--bulk-file", str(f)]
    )
    assert result.exit_code != 0
    assert "xor" in result.output.lower() or "uno y solo uno" in result.output.lower()


def test_create_bulk_parses_file_ignoring_comments_and_blanks(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    """Comments (#) y líneas vacías se filtran ANTES de enviar al API."""
    f = tmp_path / "urls.txt"
    f.write_text(
        "https://a.com\n"
        "\n"
        "# este comentario se ignora\n"
        "https://b.com\n"
        "  # comentario indentado también\n"
        "https://c.com\n"
    )
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={
                "created": [
                    _ok_lead(1, "https://a.com"),
                    _ok_lead(2, "https://b.com"),
                    _ok_lead(3, "https://c.com"),
                ],
                "skipped_duplicates": [],
                "failed": [],
            },
        )

    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads/bulk").mock(side_effect=_capture)
        result = runner.invoke(
            app, ["leads", "create", "--bulk-file", str(f)]
        )

    assert result.exit_code == 0, result.output
    body = captured["body"].decode()
    # Solo las 3 URLs limpias, sin comments ni vacías.
    assert body.count('"https://') == 3
    assert "# este comentario" not in body


def test_create_bulk_summary_in_output(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    f = tmp_path / "urls.txt"
    f.write_text("https://a.com\nhttps://b.com\nhttps://c.com\n")
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads/bulk").return_value = httpx.Response(
            200,
            json={
                "created": [_ok_lead(1, "https://a.com")],
                "skipped_duplicates": [
                    {"url": "https://b.com", "outcome": "skipped_duplicate", "lead_id": 7},
                ],
                "failed": [
                    {"url": "https://c.com", "outcome": "failed", "reason": "timeout"},
                ],
            },
        )
        result = runner.invoke(
            app, ["leads", "create", "--bulk-file", str(f)]
        )
    assert result.exit_code == 0, result.output
    assert "1 creados" in result.output
    assert "1 duplicados" in result.output
    assert "1 fallos" in result.output
    # Razón del fallo visible para diagnóstico.
    assert "timeout" in result.output


def test_create_bulk_empty_file_input_error(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    """Fichero con solo comments/vacías → CliInputError ANTES del API."""
    f = tmp_path / "urls.txt"
    f.write_text("# nada útil\n\n  # otro comment\n")
    result = runner.invoke(
        app, ["leads", "create", "--bulk-file", str(f)]
    )
    assert result.exit_code != 0
    assert "no contiene URLs" in result.output or "vacías" in result.output


def test_create_bulk_file_not_found(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    result = runner.invoke(
        app, ["leads", "create", "--bulk-file", str(tmp_path / "no-existe.txt")]
    )
    assert result.exit_code != 0
    assert "no encontrado" in result.output.lower() or "not found" in result.output.lower()


# ---------- wcm leads discard / delete (v0.12.0) ----------


def test_discard_lead_success(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.post("/api/v1/leads/3/discard").return_value = httpx.Response(
            200, json=_ok_lead(lead_id=3, url="https://x.com")
            | {"status": "discarded"},
        )
        result = runner.invoke(app, ["leads", "discard", "3"])
    assert result.exit_code == 0, result.output
    assert "#3" in result.output
    assert "discarded" in result.output


def test_delete_lead_requires_confirm(
    runner: CliRunner, authenticated
) -> None:
    """Sin --confirm el comando aborta con CliInputError ANTES de
    tocar el API."""
    result = runner.invoke(app, ["leads", "delete", "3"])
    assert result.exit_code != 0
    assert "--confirm" in result.output


def test_delete_lead_with_confirm_204(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.delete("/api/v1/leads/3").return_value = httpx.Response(204)
        result = runner.invoke(
            app, ["leads", "delete", "3", "--confirm"]
        )
    assert result.exit_code == 0, result.output
    assert "permanentemente" in result.output.lower()
