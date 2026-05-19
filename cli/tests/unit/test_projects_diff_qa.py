"""Tests de los comandos v0.16.0 del módulo `projects`:

- `wcm projects diff ID`        → tabla con visual-diffs.
- `wcm projects qa-report ID`   → resumen del último QA report.
- `wcm projects export-checklist ID --out FILE --format pdf|md`
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from wcm_cli.main import app


def _diff_row(page: str = "/", score: float = 0.92) -> dict:
    return {
        "id": 1,
        "project_id": 7,
        "page_path": page,
        "source_screenshot_url": "https://r2.example/src.png",
        "target_screenshot_url": "https://r2.example/tgt.png",
        "overlay_url": "https://r2.example/ovl.png",
        "score": score,
        "viewport_width": 1280,
        "created_at": "2026-05-19T10:00:00Z",
        "updated_at": "2026-05-19T10:00:00Z",
    }


def _qa_report() -> dict:
    return {
        "id": 1,
        "project_id": 7,
        "lighthouse_perf_desktop": 91,
        "lighthouse_perf_mobile": 65,
        "lighthouse_a11y_avg": 92,
        "lighthouse_best_practices_avg": 88,
        "lighthouse_seo_avg": 100,
        "html_validator_errors_count": 0,
        "html_validator_warnings_count": 3,
        "broken_links_count": 0,
        "total_links_checked": 42,
        "https_valid": True,
        "robots_accessible": True,
        "sitemap_accessible": True,
        "report_json": None,
        "created_at": "2026-05-19T10:00:00Z",
        "updated_at": "2026-05-19T10:00:00Z",
    }


def test_diff_sin_pages_muestra_info(
    runner: CliRunner, authenticated
) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/visual-diffs").return_value = httpx.Response(
            200, json={"project_id": 7, "pages": []}
        )
        result = runner.invoke(app, ["projects", "diff", "7"])
    assert result.exit_code == 0, result.output
    assert "Sin comparaciones visuales" in result.output


def test_diff_con_pages_renderiza_tabla(
    runner: CliRunner, authenticated
) -> None:
    payload = {"project_id": 7, "pages": [_diff_row("/contacto", 0.83)]}
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/visual-diffs").return_value = httpx.Response(
            200, json=payload
        )
        result = runner.invoke(app, ["projects", "diff", "7"])
    assert result.exit_code == 0, result.output
    assert "/contacto" in result.output
    assert "83%" in result.output
    assert "1280" in result.output


def test_qa_report_sin_data(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/qa-report").return_value = httpx.Response(
            200, json=None
        )
        result = runner.invoke(app, ["projects", "qa-report", "7"])
    assert result.exit_code == 0, result.output
    assert "Sin reporte QA" in result.output


def test_qa_report_muestra_scores(runner: CliRunner, authenticated) -> None:
    with respx.mock(base_url="http://api.test") as router:
        router.get("/api/v1/projects/7/qa-report").return_value = httpx.Response(
            200, json=_qa_report()
        )
        result = runner.invoke(app, ["projects", "qa-report", "7"])
    assert result.exit_code == 0, result.output
    assert "91/100" in result.output
    assert "65/100" in result.output
    assert "OK" in result.output


def test_export_checklist_format_invalido(
    runner: CliRunner, authenticated
) -> None:
    result = runner.invoke(
        app, ["projects", "export-checklist", "7", "--format", "docx"]
    )
    assert result.exit_code == 2
    assert "pdf" in result.output.lower() or "md" in result.output.lower()


def test_export_checklist_descarga_a_disco(
    runner: CliRunner, authenticated, tmp_path: Path
) -> None:
    out = tmp_path / "out.pdf"
    with respx.mock(base_url="http://api.test") as router:
        router.get(
            "/api/v1/projects/7/checklist/download",
            params={"format": "pdf"},
        ).return_value = httpx.Response(
            200,
            content=b"%PDF-1.4 fake content",
            headers={"content-type": "application/pdf"},
        )
        result = runner.invoke(
            app,
            [
                "projects",
                "export-checklist",
                "7",
                "--out",
                str(out),
                "--format",
                "pdf",
            ],
        )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")
    assert "exportado" in result.output.lower()
