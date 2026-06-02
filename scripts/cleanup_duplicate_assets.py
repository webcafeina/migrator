"""Detecta y elimina assets duplicados en la BD.

Mitigación para WCM-039: cuando `task_acks_late=True` + restart del worker
provocan **re-ejecución del orchestrator desde cero**, el `ScraperOriginAgent`
crea de nuevo todos los assets (676 → 1351 en E2E v0.27.0 mariya.design).

Criterio de duplicado: mismo `(project_id, original_url)`. Si hay más de
una fila, mantén SOLO la mejor candidata (en orden):
  1. La que tiene `wp_attachment_id IS NOT NULL` (ya subida a WP).
  2. La que tiene `r2_key IS NOT NULL` (en R2).
  3. La de `id` más bajo (más antigua).

Las demás se borran. ON DELETE CASCADE limpia referencias internas.

Uso:
    python scripts/cleanup_duplicate_assets.py <project_id> [--dry-run]
    python scripts/cleanup_duplicate_assets.py --all [--dry-run]

`--dry-run` (default) muestra lo que borraría sin tocarla BD.
Pasar `--apply` para ejecutar las eliminaciones realmente.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path


def _load_env() -> None:
    """Carga .env con strip de comillas (mismo comportamiento dotenv)."""
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def _connect():
    import psycopg  # noqa: PLC0415

    url = os.environ["DATABASE_URL"]
    # Sin variantes asyncpg / psycopg+driver — usar conexión nativa.
    url = url.replace("+asyncpg", "").replace("postgresql+psycopg", "postgresql")
    return psycopg.connect(url, autocommit=False)


def _best_keeper(rows: list[dict]) -> int:
    """Devuelve el `id` del asset a CONSERVAR del grupo de duplicados.

    Prioridad: wp_attachment_id > r2_key > id mínimo.
    """
    # 1. Con wp_attachment_id
    wp = [r for r in rows if r.get("wp_attachment_id") is not None]
    if wp:
        return min(wp, key=lambda r: r["id"])["id"]
    # 2. Con r2_key
    r2 = [r for r in rows if r.get("r2_key")]
    if r2:
        return min(r2, key=lambda r: r["id"])["id"]
    # 3. Id mínimo
    return min(rows, key=lambda r: r["id"])["id"]


def find_duplicate_groups(conn, project_id: int) -> dict[str, list[dict]]:
    """Devuelve dict `original_url → [rows...]` con grupos de >1 row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, project_id, original_url, hash, wp_attachment_id, r2_key
            FROM assets
            WHERE project_id = %s
            ORDER BY original_url, id
            """,
            (project_id,),
        )
        cols = [d.name for d in cur.description]
        all_rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        groups[r["original_url"]].append(r)
    return {url: rows for url, rows in groups.items() if len(rows) > 1}


def cleanup_project(conn, project_id: int, *, apply: bool) -> dict:
    """Elimina duplicados de un proyecto. Devuelve summary stats."""
    groups = find_duplicate_groups(conn, project_id)
    if not groups:
        return {
            "project_id": project_id,
            "duplicate_urls": 0,
            "rows_to_delete": 0,
            "applied": False,
        }
    ids_to_delete: list[int] = []
    for _url, rows in groups.items():
        keeper = _best_keeper(rows)
        for r in rows:
            if r["id"] != keeper:
                ids_to_delete.append(r["id"])

    if apply and ids_to_delete:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM assets WHERE id = ANY(%s)",
                (ids_to_delete,),
            )
        conn.commit()

    return {
        "project_id": project_id,
        "duplicate_urls": len(groups),
        "rows_to_delete": len(ids_to_delete),
        "applied": apply,
    }


def list_all_project_ids(conn) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT project_id FROM assets ORDER BY project_id")
        return [r[0] for r in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", nargs="?", type=int, help="Project id; omitir con --all")
    parser.add_argument("--all", action="store_true", help="Procesa todos los proyectos")
    parser.add_argument("--apply", action="store_true", help="Aplica las eliminaciones (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Solo simula (default)")
    args = parser.parse_args()

    if not args.project_id and not args.all:
        parser.error("Indica project_id o --all")
    if args.project_id and args.all:
        parser.error("project_id Y --all son mutuamente excluyentes")

    _load_env()
    conn = _connect()
    apply = bool(args.apply) and not args.dry_run

    project_ids = list_all_project_ids(conn) if args.all else [args.project_id]
    total_rows = 0
    for pid in project_ids:
        summary = cleanup_project(conn, pid, apply=apply)
        if summary["rows_to_delete"] > 0:
            verb = "Borrados" if summary["applied"] else "Borraría"
            print(
                f"Project {summary['project_id']}: "
                f"{summary['duplicate_urls']} URLs duplicadas, "
                f"{verb} {summary['rows_to_delete']} filas"
            )
            total_rows += summary["rows_to_delete"]
        else:
            print(f"Project {summary['project_id']}: sin duplicados")
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n[{mode}] Total: {total_rows} filas afectadas")
    if not apply and total_rows > 0:
        print("→ Re-ejecutar con `--apply` para borrar realmente.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
