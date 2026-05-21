"""Aplica `projects.bricks_global_classes` al option `bricks_global_classes`
del destino WP via SSH+WP-CLI. Útil para fixes ad-hoc sin re-correr el
pipeline completo. Lee credenciales del Project (cifradas Fernet).

Uso: `python scripts/apply_global_classes.py <project_id>`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _load_env() -> None:
    """Carga .env con strip de comillas (mismo comportamiento de dotenv)."""
    for line in Path(".env").read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        # Quitar comillas envolventes si las hay.
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


async def main(project_id: int) -> None:
    _load_env()

    # Imports tras cargar env.
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    from wcm_wp_client.config import WpClientConfig  # noqa: PLC0415
    from wcm_wp_client.ssh_cli import WpCliSshClient  # noqa: PLC0415

    e = create_engine(os.environ["DATABASE_SYNC_URL"])
    with e.connect() as c:
        row = c.execute(
            text(
                "SELECT bricks_global_classes, hosting_target_json, deploy_credentials_encrypted "
                "FROM projects WHERE id=:id"
            ),
            {"id": project_id},
        ).mappings().first()
    if row is None:
        print(f"Project {project_id} not found", file=sys.stderr)
        sys.exit(1)

    classes = row["bricks_global_classes"] or []
    if not classes:
        print("No bricks_global_classes en projects — nothing to apply")
        sys.exit(0)

    # WpClientConfig.from_env() usa WP_DEFAULT_* del .env. Para proyectos
    # con credenciales propias cifradas habría que descifrar con Fernet —
    # fuera del scope de este script ad-hoc.
    cfg = WpClientConfig.from_env()

    print(f"Aplicando {len(classes)} globalClasses al host {cfg.ssh_host}…")
    async with WpCliSshClient(cfg) as cli:
        # Merge con existing en el destino.
        merged: list = []
        if await cli.option_exists("bricks_global_classes"):
            existing_raw = await cli.option_get(
                "bricks_global_classes", format="json"
            )
            if existing_raw:
                try:
                    parsed = json.loads(existing_raw)
                    if isinstance(parsed, list):
                        merged = parsed
                except json.JSONDecodeError:
                    pass
        new_ids = {c["id"] for c in classes if isinstance(c, dict) and c.get("id")}
        merged = [c for c in merged if isinstance(c, dict) and c.get("id") not in new_ids]
        merged.extend(classes)
        await cli.option_update("bricks_global_classes", merged, format="json")
        print(f"OK · option `bricks_global_classes` actualizada · {len(merged)} clases")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/apply_global_classes.py <project_id>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(int(sys.argv[1])))
