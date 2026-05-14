"""Comando para lanzar campañas de prospección."""

from __future__ import annotations

from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient

app = typer.Typer(help="Campañas de prospección")


@app.command("launch")
def launch_campaign(
    sector: Annotated[str, typer.Option(help="Sector (p. ej. 'restauración')")],
    region: Annotated[str, typer.Option(help="Región / CCAA / provincia")],
    target: Annotated[int, typer.Option(help="Objetivo de leads a descubrir")] = 50,
) -> None:
    """Encola una campaña de prospección.

    El worker la procesa (en Fase 9 cuando ProspectorAgent esté implementado).
    Hasta entonces, el endpoint encola pero el agent es stub.
    """
    client = ApiClient()
    result = client.post(
        "/api/v1/campaigns/launch",
        json={"sector": sector, "region": region, "target_count": target},
    )
    output.success(
        f"Campaña encolada: task {result['task_id']} "
        f"(sector={sector}, region={region}, target={target})"
    )
    output.info(
        "El worker descubrirá leads vía Google Places y los pasará por "
        "fingerprint + enrich automáticamente."
    )
