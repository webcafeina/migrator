"""Comandos sobre leads."""

from __future__ import annotations

from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient

app = typer.Typer(help="Gestión de leads")


@app.command("list")
def list_leads(
    sector: Annotated[str | None, typer.Option(help="Filtro por sector")] = None,
    region: Annotated[str | None, typer.Option(help="Filtro por región")] = None,
    builder: Annotated[str | None, typer.Option(help="Filtro por builder: wix|hostinger_ai|webflow|...")] = None,
    status: Annotated[str | None, typer.Option(help="Filtro por status del lead")] = None,
    min_score: Annotated[int, typer.Option(help="Score mínimo (0-100)")] = 0,
    limit: Annotated[int, typer.Option(help="Máximo de resultados")] = 50,
) -> None:
    """Lista leads con filtros opcionales."""
    params = {"min_score": min_score, "limit": limit}
    if sector:
        params["sector"] = sector
    if region:
        params["region"] = region
    if builder:
        params["builder"] = builder
    if status:
        params["status"] = status

    client = ApiClient()
    leads = client.get("/api/v1/leads", params=params)

    if not leads:
        output.info("Sin leads que coincidan con los filtros.")
        return

    output.render_table(
        f"Leads ({len(leads)})",
        ["id", "url", "sector", "region", "builder", "conf", "score", "status"],
        [
            [
                lead["id"],
                lead["url"],
                lead.get("sector") or "—",
                lead.get("region") or "—",
                (lead.get("builder_detected") or "—"),
                f"{lead['builder_confidence']:.2f}"
                if lead.get("builder_confidence") is not None
                else "—",
                lead["score"],
                lead["status"],
            ]
            for lead in leads
        ],
        json_payload=leads,
    )


@app.command("get")
def get_lead(lead_id: Annotated[int, typer.Argument(help="ID del lead")]) -> None:
    """Detalle completo de un lead."""
    client = ApiClient()
    lead = client.get(f"/api/v1/leads/{lead_id}")
    if output.is_json_mode():
        output.emit_json(lead)
    else:
        output.key_value({
            "id": lead["id"],
            "url": lead["url"],
            "empresa": lead.get("business_name") or "—",
            "sector": lead.get("sector") or "—",
            "región": lead.get("region") or "—",
            "builder": lead.get("builder_detected") or "—",
            "confianza": f"{lead['builder_confidence']:.2f}" if lead.get("builder_confidence") is not None else "—",
            "emails": ", ".join(lead.get("emails") or []) or "—",
            "teléfonos": ", ".join(lead.get("phones") or []) or "—",
            "score": lead["score"],
            "status": lead["status"],
            "creado": lead["created_at"],
        })


@app.command("refingerprint")
def refingerprint_lead(lead_id: Annotated[int, typer.Argument()]) -> None:
    """Encola re-fingerprint de un lead (worker lo procesará)."""
    client = ApiClient()
    result = client.post(f"/api/v1/leads/{lead_id}/refingerprint")
    output.success(f"Encolada task {result['task_id']} para lead {lead_id}")


@app.command("enrich")
def enrich_lead(
    lead_id: Annotated[int, typer.Argument(help="ID del lead a enriquecer")],
    skip_embedding: Annotated[
        bool, typer.Option("--skip-embedding", help="Saltar embedding (más rápido)")
    ] = False,
) -> None:
    """Encola enriquecimiento (emails, phones, socials, embedding) de un lead."""
    client = ApiClient()
    params = {"skip_embedding": "true"} if skip_embedding else None
    result = client.post(f"/api/v1/leads/{lead_id}/enrich", params=params)
    output.success(f"Encolada task {result['task_id']} para lead {lead_id}")
