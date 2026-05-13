"""Comando `wcm deploy` — stub porque depende de Fase 12 (Infra/Deploy).

En Fase 12 ejecutará `infra/deploy/deploy.sh` con el env correspondiente
+ pre-check con ssh al servidor + post-check con smoke test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wcm_cli import output

app = typer.Typer(help="Deploy a servidor")


@app.callback(invoke_without_command=True)
def deploy(
    env: Annotated[str, typer.Option(help="Entorno: staging | production")] = "staging",
) -> None:
    """Lanza el deploy al entorno indicado."""
    script_path = Path("infra/deploy/deploy.sh")
    output.warning(
        f"`wcm deploy --env {env}` aún no implementado (Fase 12 — Infra/Deploy)."
    )
    output.info("Cuando esté listo, ejecutará:")
    output.info(f"  bash {script_path} --env={env}")
    output.info("")
    output.info("Mientras tanto, despliega manualmente con `infra/whm-setup/` desde el servidor.")
    raise typer.Exit(code=1)
