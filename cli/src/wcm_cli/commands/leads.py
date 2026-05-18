"""Comandos sobre leads."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient
from wcm_cli.errors import CliApiError, CliInputError

app = typer.Typer(help="Gestión de leads")


@app.command("create")
def create_lead(
    url: Annotated[
        str | None,
        typer.Option(help="URL del lead. Excluyente con --bulk-file."),
    ] = None,
    sector: Annotated[
        str | None, typer.Option(help="Sector aplicado al lead/batch")
    ] = None,
    region: Annotated[
        str | None, typer.Option(help="Región aplicada al lead/batch")
    ] = None,
    country: Annotated[
        str, typer.Option(help="Código ISO de país (2 letras)")
    ] = "ES",
    business_name: Annotated[
        str | None, typer.Option(help="Nombre comercial (solo single)")
    ] = None,
    bulk_file: Annotated[
        Path | None,
        typer.Option(
            "--bulk-file",
            help="Fichero con 1 URL por línea (excluyente con --url). "
            "Líneas vacías y las que empiezan con # se ignoran.",
        ),
    ] = None,
) -> None:
    """Alta manual de uno o varios leads.

    Tras crear, el sistema encadena fingerprint + enrich
    automáticamente. La base jurídica RGPD aplicada es art. 6.1.f
    (interés legítimo B2B) — misma que la prospección automática.
    """
    if (url is None) == (bulk_file is None):
        raise CliInputError(
            "Usa --url XOR --bulk-file (uno y solo uno).",
            hint=(
                "Ej. alta única: wcm leads create --url https://foo.com\n"
                "Ej. alta bulk:  wcm leads create --bulk-file urls.txt"
            ),
        )

    client = ApiClient()

    if url is not None:
        body: dict[str, str] = {"url": url, "country": country}
        if sector:
            body["sector"] = sector
        if region:
            body["region"] = region
        if business_name:
            body["business_name"] = business_name
        try:
            lead = client.post("/api/v1/leads", json=body)
        except CliApiError as e:
            existing = e.details.get("existing_lead_id")
            if existing is not None:
                output.error(
                    f"URL duplicada · lead existente #{existing}"
                )
                raise typer.Exit(code=1) from None
            raise
        output.success(f"Lead #{lead['id']} creado · {lead['url']}")
        return

    # bulk
    assert bulk_file is not None  # noqa: S101 — narrowing para mypy
    if not bulk_file.exists():
        raise CliInputError(f"Fichero no encontrado: {bulk_file}")
    urls = [
        line.strip()
        for line in bulk_file.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not urls:
        raise CliInputError(
            "El fichero no contiene URLs válidas (solo líneas vacías o comments)."
        )
    body_bulk: dict[str, object] = {"urls": urls, "country": country}
    if sector:
        body_bulk["sector"] = sector
    if region:
        body_bulk["region"] = region

    result = client.post("/api/v1/leads/bulk", json=body_bulk)
    output.success(
        f"{len(result['created'])} creados · "
        f"{len(result['skipped_duplicates'])} duplicados · "
        f"{len(result['failed'])} fallos"
    )
    if result["failed"]:
        # Mostrar primeras 3 razones de fallo para diagnóstico rápido.
        for fail in result["failed"][:3]:
            output.info(f"  fail · {fail['url']} · {fail.get('reason', '?')}")


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


@app.command("discard")
def discard_lead(
    lead_id: Annotated[int, typer.Argument(help="ID del lead a descartar")],
) -> None:
    """Soft delete: marca el lead como DISCARDED. Reversible —
    cualquier PATCH del status restaura. El listado oculta DISCARDED
    por defecto en dashboard y CLI."""
    client = ApiClient()
    lead = client.post(f"/api/v1/leads/{lead_id}/discard")
    output.success(f"Lead #{lead['id']} descartado (status={lead['status']})")


@app.command("delete")
def delete_lead(
    lead_id: Annotated[int, typer.Argument(help="ID del lead a borrar")],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Obligatorio para confirmar el hard delete (CASCADE).",
        ),
    ] = False,
) -> None:
    """Hard delete: borra el lead + sus enriquecimientos + sequences
    con CASCADE. Irreversible. Usa `wcm leads discard ID` si solo
    quieres ocultarlo del listado."""
    if not confirm:
        raise CliInputError(
            "Borrado definitivo requiere --confirm.",
            hint=(
                "Para descartar (reversible) usa `wcm leads discard ID`.\n"
                "Para borrado real ejecuta `wcm leads delete ID --confirm`."
            ),
        )
    client = ApiClient()
    client.delete(f"/api/v1/leads/{lead_id}")
    output.success(f"Lead #{lead_id} borrado permanentemente (CASCADE)")


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
