"""Tests del script scripts/cleanup_duplicate_assets.py (v0.28.0 B7)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def _load_script_module():
    """Carga el script standalone como módulo testeable."""
    script_path = Path(__file__).parents[2] / "scripts" / "cleanup_duplicate_assets.py"
    spec = importlib.util.spec_from_file_location("cleanup_dup_assets", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -----------------------------------------------------------------------------
# _best_keeper — prioriza wp_attachment_id > r2_key > id mínimo
# -----------------------------------------------------------------------------


def test_best_keeper_prefers_wp_attachment_id() -> None:
    mod = _load_script_module()
    rows = [
        {"id": 1, "wp_attachment_id": None, "r2_key": "x/1.jpg"},
        {"id": 2, "wp_attachment_id": 999, "r2_key": "x/2.jpg"},
        {"id": 3, "wp_attachment_id": None, "r2_key": None},
    ]
    assert mod._best_keeper(rows) == 2


def test_best_keeper_falls_back_to_r2_key() -> None:
    mod = _load_script_module()
    rows = [
        {"id": 5, "wp_attachment_id": None, "r2_key": None},
        {"id": 6, "wp_attachment_id": None, "r2_key": "x/6.jpg"},
        {"id": 7, "wp_attachment_id": None, "r2_key": "x/7.jpg"},
    ]
    # 6 es el más bajo con r2_key
    assert mod._best_keeper(rows) == 6


def test_best_keeper_falls_back_to_min_id() -> None:
    mod = _load_script_module()
    rows = [
        {"id": 10, "wp_attachment_id": None, "r2_key": None},
        {"id": 11, "wp_attachment_id": None, "r2_key": None},
        {"id": 12, "wp_attachment_id": None, "r2_key": None},
    ]
    assert mod._best_keeper(rows) == 10


def test_best_keeper_wp_wins_over_r2() -> None:
    """Aunque r2_key esté en row con id más bajo, wp_attachment_id gana."""
    mod = _load_script_module()
    rows = [
        {"id": 1, "wp_attachment_id": None, "r2_key": "x/1.jpg"},
        {"id": 2, "wp_attachment_id": 100, "r2_key": None},
    ]
    assert mod._best_keeper(rows) == 2


# -----------------------------------------------------------------------------
# find_duplicate_groups — con mock de cursor psycopg
# -----------------------------------------------------------------------------


def _mock_conn_with_rows(rows: list[tuple]) -> MagicMock:
    """Construye una conn mock con cursor que devuelve `rows` tras fetchall."""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [
        MagicMock(name="id"), MagicMock(name="project_id"),
        MagicMock(name="original_url"), MagicMock(name="hash"),
        MagicMock(name="wp_attachment_id"), MagicMock(name="r2_key"),
    ]
    # asignar atributos `.name` correctos (MagicMock no infiere)
    cur.description[0].name = "id"
    cur.description[1].name = "project_id"
    cur.description[2].name = "original_url"
    cur.description[3].name = "hash"
    cur.description[4].name = "wp_attachment_id"
    cur.description[5].name = "r2_key"
    cur.fetchall.return_value = rows
    conn.cursor.return_value.__enter__.return_value = cur
    return conn


def test_find_duplicate_groups_returns_only_groups_with_more_than_one() -> None:
    mod = _load_script_module()
    rows = [
        (1, 30, "https://wix.com/hero.jpg", "hash1", None, None),
        (2, 30, "https://wix.com/hero.jpg", "hash1", None, None),  # dup
        (3, 30, "https://wix.com/unique.jpg", "hash2", None, None),
    ]
    conn = _mock_conn_with_rows(rows)
    groups = mod.find_duplicate_groups(conn, project_id=30)
    assert "https://wix.com/hero.jpg" in groups
    assert "https://wix.com/unique.jpg" not in groups
    assert len(groups["https://wix.com/hero.jpg"]) == 2


def test_find_duplicate_groups_empty_when_no_duplicates() -> None:
    mod = _load_script_module()
    rows = [
        (1, 30, "https://x.com/1.jpg", "h1", None, None),
        (2, 30, "https://x.com/2.jpg", "h2", None, None),
    ]
    conn = _mock_conn_with_rows(rows)
    groups = mod.find_duplicate_groups(conn, project_id=30)
    assert groups == {}


# -----------------------------------------------------------------------------
# cleanup_project — dry-run vs apply
# -----------------------------------------------------------------------------


def test_cleanup_project_dry_run_does_not_execute_delete() -> None:
    mod = _load_script_module()
    rows = [
        (1, 30, "https://wix.com/hero.jpg", "h1", None, None),
        (2, 30, "https://wix.com/hero.jpg", "h1", None, None),
    ]
    conn = _mock_conn_with_rows(rows)
    summary = mod.cleanup_project(conn, 30, apply=False)
    assert summary == {
        "project_id": 30,
        "duplicate_urls": 1,
        "rows_to_delete": 1,
        "applied": False,
    }
    # commit no llamado
    conn.commit.assert_not_called()


def test_cleanup_project_apply_calls_delete_and_commit() -> None:
    mod = _load_script_module()
    rows = [
        (1, 30, "https://wix.com/hero.jpg", "h1", None, None),
        (2, 30, "https://wix.com/hero.jpg", "h1", 999, None),  # con WP id → keeper
    ]
    conn = _mock_conn_with_rows(rows)
    summary = mod.cleanup_project(conn, 30, apply=True)
    assert summary["applied"] is True
    assert summary["rows_to_delete"] == 1  # se borra el id=1 (sin wp_id)
    conn.commit.assert_called_once()


def test_cleanup_project_no_duplicates_returns_zero() -> None:
    mod = _load_script_module()
    rows = [
        (1, 30, "https://x.com/a.jpg", "h1", None, None),
    ]
    conn = _mock_conn_with_rows(rows)
    summary = mod.cleanup_project(conn, 30, apply=True)
    assert summary["rows_to_delete"] == 0
    conn.commit.assert_not_called()
