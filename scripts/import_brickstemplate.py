"""Importa el catálogo de brickstemplate.com como JSON Bricks local.

Sprint v0.25.0 B4. Pre-requisito del pipeline Templates: poblar
`docs/templates/brickstemplate/` con templates curados que el
`SectionPicker` + `SlotMapper` consumen.

Brickstemplate.com expone su catálogo via "Remote Templates URL"
nativo de Bricks Builder. La URL canónica es del tipo:
    https://brickstemplate.com/wp-json/bricks/v1/templates

Endpoint requiere `password` header con la licencia del operador
(la misma que se pega en `Bricks > Settings > Templates > Remote
Templates URL` desde el editor).

Uso:
    export BRICKSTEMPLATE_LICENSE="<tu_password>"
    python scripts/import_brickstemplate.py [--out docs/templates/brickstemplate] [--limit 50]

Salida:
    docs/templates/brickstemplate/
      sections-index.json       ← metadata de TODOS los templates
      hero/hero-XYZ-001.json    ← un JSON por template
      features/features-XYZ.json
      ...

CURADO MANUAL POST-IMPORT:
El operador debe editar `sections-index.json` para añadir/refinar:
- `vibe`: minimalist | playful | corporate | artistic | bold
- `fits_sectors`: ["agency", "restaurant", "fitness", ...]
- `fits_tones`: ["formal", "casual", "premium", ...]
- `slot_map`: paths JSONPath → keys del Brief

Sin curar, los templates funcionan pero con bajo matching (todos
neutros → SectionPicker elige cualquiera).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("import_brickstemplate")

#: Endpoint canónico Bricks Remote Templates API (verificado contra
#: brickstemplate.com 2026-05-25). El plugin Bricks 2.x espera:
#: GET /wp-json/bricks/v1/get-templates?site=<DESTINO>&password=<LICENCIA>
DEFAULT_API_URL = "https://brickstemplate.com/wp-json/bricks/v1/get-templates"

#: v0.27.0 B8 — fuente alternativa BricksPlus. URL del dominio API
#: NO confirmada (bricksplus.com no expone WP REST). Cuando el operador
#: compre la licencia, obtendrá el URL del panel BricksPlus y deberá
#: setear BRICKSPLUS_API_URL en .env con el valor correcto.
#: Placeholder por ahora.
BRICKSPLUS_DEFAULT_API_URL = (
    "https://bricksplus.com/wp-json/bricks/v1/get-templates"
)

#: Configuración por source. Cada source mapea a (env_url, env_license,
#: default_url, default_out_dir).
_SOURCE_CONFIGS: dict[str, dict[str, str]] = {
    "brickstemplate": {
        "env_url": "BRICKSTEMPLATE_API_URL",
        "env_license": "BRICKSTEMPLATE_LICENSE",
        "default_url": DEFAULT_API_URL,
        "default_out": "docs/templates/brickstemplate",
    },
    "bricksplus": {
        "env_url": "BRICKSPLUS_API_URL",
        "env_license": "BRICKSPLUS_LICENSE",
        "default_url": BRICKSPLUS_DEFAULT_API_URL,
        "default_out": "docs/templates/bricksplus",
    },
}

#: Mapping de categorías brickstemplate → nuestras categorías canónicas.
#: Si brickstemplate categoriza algo distinto, mapeamos aquí. El resto
#: pasa tal cual.
CATEGORY_NORMALIZE: dict[str, str] = {
    "headers": "header",
    "heroes": "hero",
    "features": "features",
    "ctas": "cta",
    "footers": "footer",
    "testimonials": "testimonials",
    "pricings": "pricing",
    "galleries": "gallery",
    "contacts": "contact_form",
    "services": "services",
}


def _slugify(value: str) -> str:
    """`Hero Minimalist 001` → `hero-minimalist-001`."""
    v = value.lower().strip()
    v = re.sub(r"[^a-z0-9]+", "-", v)
    return v.strip("-")


def _normalize_category(raw: str) -> str:
    """Mapea categoría brickstemplate → nuestra canónica. Lowercase."""
    low = (raw or "").lower().strip()
    return CATEGORY_NORMALIZE.get(low, low)


def fetch_catalog(
    api_url: str, license_password: str, requester_site: str,
) -> list[dict[str, Any]]:
    """GET al endpoint Bricks Remote Templates con query string nativo.

    Forma verificada contra brickstemplate.com (2026-05-25):
    `GET /wp-json/bricks/v1/get-templates?site=<DESTINO>&password=<LICENCIA>`

    El parámetro `site` lo valida brickstemplate.com (whitelist por dominio
    si el owner lo activó). Pasamos la URL del WP destino del operador
    (típicamente test-migrator.webcafeina.com).

    Devuelve lista de templates JSON tal como los expone el endpoint.
    Cada item suele tener: {name, category, content, settings, ...}.
    """
    log.info("fetch_catalog_start", extra={"url": api_url, "site": requester_site})
    try:
        resp = httpx.get(
            api_url,
            params={"site": requester_site, "password": license_password},
            timeout=60.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        log.error("fetch_catalog_http_error", extra={"error": str(e)[:300]})
        raise SystemExit(f"Error HTTP: {e}") from e
    # Bricks devuelve HTTP 200 con {"error": {...}} aunque haya error de
    # auth. Detectar y mapear a SystemExit explicativo.
    if resp.status_code == 200:
        try:
            preview = resp.json()
        except ValueError:
            preview = None
        if isinstance(preview, dict) and preview.get("error"):
            code = preview["error"].get("code", "unknown")
            message = preview["error"].get("message", "")
            if code == "remote_templates_password_incorrect":
                raise SystemExit(
                    f"Password (licencia) incorrecta para {api_url}. "
                    "Verifica BRICKSTEMPLATE_LICENSE."
                )
            if code == "no_site_url":
                raise SystemExit(
                    "Falta `site` en la petición. Usa --requester-site o "
                    "asegúrate de tener WP_DEFAULT_SITE_URL en .env."
                )
            if code == "not_whitelisted":
                raise SystemExit(
                    f"El dominio {requester_site!r} no está en la whitelist del "
                    "owner del catálogo Bricks. Pídele que añada tu URL en "
                    "Bricks → Settings → Templates → My Templates Whitelist."
                )
            raise SystemExit(f"Bricks API error [{code}]: {message}")
    if resp.status_code == 401:
        raise SystemExit(
            "401 Unauthorized — verifica el endpoint."
        )
    if resp.status_code != 200:
        raise SystemExit(
            f"HTTP {resp.status_code} — endpoint no devuelve catálogo: "
            f"{resp.text[:300]}"
        )
    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        raise SystemExit(f"Response no es JSON: {e}") from e
    # Brickstemplate.com responde con `{templates: [...]}` o lista directa.
    if isinstance(data, dict) and "templates" in data:
        return data["templates"]
    if isinstance(data, list):
        return data
    raise SystemExit(
        f"Shape inesperado: {type(data).__name__} — esperaba list o "
        "dict con key 'templates'."
    )


def normalize_template(raw: dict[str, Any], idx: int) -> dict[str, Any] | None:
    """Convierte template brickstemplate → shape canónica para nuestro
    SectionPicker. Devuelve None si el template no es procesable
    (sin content array)."""
    name = raw.get("name") or raw.get("title") or f"template-{idx:04d}"
    category_raw = raw.get("category") or raw.get("type") or "uncategorized"
    category = _normalize_category(category_raw)
    content = raw.get("content")
    if not isinstance(content, list) or not content:
        log.warning(
            "template_skipped_no_content",
            extra={"name": name, "raw_keys": list(raw.keys())[:10]},
        )
        return None
    slug = _slugify(name)
    template_id = f"{category}-{slug}-{idx:03d}"
    return {
        "id": template_id,
        "category": category,
        "name": name,
        "file": f"{category}/{template_id}.json",
        # Metadata CURADA: dejamos vacías para que el operador rellene.
        # Sin curar, SectionPicker hace fallback a "cualquier candidato".
        "vibe": "",
        "fits_sectors": [],
        "fits_tones": [],
        # slot_map vacío: el operador define qué paths corresponden a
        # qué keys del Brief. Sin slot_map, SlotMapper deja los strings
        # placeholder originales del template.
        "slot_map": {},
        # Metadata informativa (no usada por el picker).
        "n_elements": len(content),
        "_original_payload": {
            "settings": raw.get("settings"),
            "thumbnail": raw.get("thumbnail"),
            "preview_url": raw.get("preview_url"),
        },
    }


def write_template_file(
    out_dir: Path, template_meta: dict[str, Any], raw: dict[str, Any]
) -> None:
    """Persiste el JSON Bricks del template en `out_dir/<file>`."""
    template_path = out_dir / template_meta["file"]
    template_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "id": template_meta["id"],
            "category": template_meta["category"],
            "name": template_meta["name"],
            "source": "brickstemplate.com",
        },
        "content": raw["content"],
    }
    with template_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def write_sections_index(
    out_dir: Path, templates_meta: list[dict[str, Any]]
) -> None:
    """Escribe `sections-index.json` con metadata de todos los templates.

    Estructura compatible con `load_sections_index` del SectionPicker.
    """
    index_path = out_dir / "sections-index.json"
    payload = {
        "_meta": {
            "description": (
                "Catálogo brickstemplate.com importado. Los campos "
                "`vibe`, `fits_sectors`, `fits_tones`, `slot_map` están "
                "VACÍOS — el operador debe curarlos manualmente. Sin "
                "curar, SectionPicker funciona pero con bajo matching."
            ),
            "version": "brickstemplate-import-v1",
            "n_templates": len(templates_meta),
        },
        "templates": templates_meta,
    }
    with index_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    parser = argparse.ArgumentParser(
        description=(
            "Importa catálogo Bricks (brickstemplate.com o BricksPlus) "
            "a JSON local. v0.27.0 B8 — multi-source."
        )
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=list(_SOURCE_CONFIGS.keys()),
        default="brickstemplate",
        help=(
            "Catálogo a importar. brickstemplate (default) o bricksplus. "
            "Cada source usa sus propios env vars: "
            "BRICKSTEMPLATE_API_URL/LICENSE o BRICKSPLUS_API_URL/LICENSE."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Directorio de salida. Default depende de --source: "
            "docs/templates/brickstemplate o docs/templates/bricksplus."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Límite de templates a importar (0 = todos)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help=(
            "Override URL del endpoint. Si no, usa env "
            "BRICKSTEMPLATE_API_URL/BRICKSPLUS_API_URL según --source."
        ),
    )
    parser.add_argument(
        "--requester-site",
        type=str,
        default=None,
        help=(
            "URL del WP destino que solicita los templates (param `site` "
            "obligatorio que Bricks valida contra su whitelist). "
            "Default: WP_DEFAULT_SITE_URL del .env."
        ),
    )
    args = parser.parse_args(argv)

    source_cfg = _SOURCE_CONFIGS[args.source]
    if args.out is None:
        args.out = Path(source_cfg["default_out"])
    if args.api_url is None:
        args.api_url = os.environ.get(
            source_cfg["env_url"], source_cfg["default_url"]
        )

    license_password = os.environ.get(source_cfg["env_license"], "").strip()
    if not license_password:
        log.error(
            f"Sin {source_cfg['env_license']}. Configurar:\n"
            f"  export {source_cfg['env_license']}='<tu_password>'\n"
            f"Tu password es el mismo que pegas en Bricks > Settings > "
            "Templates > Remote Templates URL (lo recibiste por email "
            "al comprar la suscripción)."
        )
        return 1

    requester_site = args.requester_site or os.environ.get(
        "WP_DEFAULT_SITE_URL", ""
    ).strip()
    if not requester_site:
        log.error(
            "Sin --requester-site ni WP_DEFAULT_SITE_URL. Bricks API requiere "
            "el dominio que solicita los templates."
        )
        return 1

    args.out.mkdir(parents=True, exist_ok=True)

    raw_templates = fetch_catalog(args.api_url, license_password, requester_site)
    log.info("catalog_fetched", extra={"n_raw_templates": len(raw_templates)})

    if args.limit > 0:
        raw_templates = raw_templates[: args.limit]

    templates_meta: list[dict[str, Any]] = []
    skipped = 0
    for idx, raw in enumerate(raw_templates, start=1):
        meta = normalize_template(raw, idx)
        if meta is None:
            skipped += 1
            continue
        write_template_file(args.out, meta, raw)
        templates_meta.append(meta)

    write_sections_index(args.out, templates_meta)

    log.info(
        "import_complete",
        extra={
            "n_written": len(templates_meta),
            "n_skipped": skipped,
            "out_dir": str(args.out),
        },
    )
    print(
        f"\n✓ Importados {len(templates_meta)} templates en {args.out}.\n"
        f"  Skipped: {skipped}\n"
        f"\nPRÓXIMO PASO: editar {args.out / 'sections-index.json'} para "
        f"añadir metadata curada (vibe, fits_sectors, fits_tones, slot_map)\n"
        f"por template. Sin curar, SectionPicker fallback a 'cualquier "
        f"candidato' (bajo matching).\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
