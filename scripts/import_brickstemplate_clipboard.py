"""Importa el catálogo de brickstemplate.com vía clipboard listener.

v0.28.0 (B12). Reemplaza el `import_brickstemplate.py` que asumía Remote
Templates API — el soporte de brickstemplate confirmó que NO la usan.

Workflow del operador:
1. Lanza el script con categoría activa:
       python scripts/import_brickstemplate_clipboard.py --category footer
2. Va al área de miembros, clic en botón "copy" de cada template.
3. El script detecta clipboard con shape Bricks (`source: bricksCopiedElements`),
   parsea, valida, persiste en `docs/templates/brickstemplate/<category>/<slug>.json`
   y actualiza `sections-index.json`.
4. Para cambiar categoría: detener (Ctrl+C) y relanzar con `--category hero`
   o usar el comando inline `cat:<nombre>` en el terminal (no implementado
   en v0 — relanzar es suficiente).

Features:
- **Auto-detección de Bricks JSON**: ignora cualquier otra cosa en clipboard.
- **Deduplicación por SHA256** del `content`: si ya existe, se salta.
- **Naming desde `label`**: kebab-case con sufijo `-N` ante colisión.
- **Estado persistente**: al reanudar cuenta los `.json` en disco.
- **Validación de shape**: alerta si detecta keys snake_case (anti-patrón).

Dependencia: `pyperclip` (instalable solo en scripts/, no en worker prod).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import pyperclip
except ImportError:
    # Lazy import: el script se puede importar para testear funciones puras
    # (parse_bricks_payload, slugify, etc.) sin pyperclip instalado. Solo
    # `main()` requiere el módulo realmente.
    pyperclip = None  # type: ignore[assignment]


CATALOG_ROOT = Path("docs/templates/brickstemplate")
INDEX_PATH = CATALOG_ROOT / "sections-index.json"

#: Marcador de shape Bricks copy/paste — único y robusto.
BRICKS_SOURCE_MARKER = "bricksCopiedElements"

#: Categorías oficiales de brickstemplate (las que mencionó el operador).
KNOWN_CATEGORIES = {
    "back-to-top", "banner", "bio-links", "brands", "button", "call-to-action",
    "cart", "coming-soon", "contact-us", "counter", "email-opt-in", "error-page",
    "faqs", "features", "footer", "free", "header", "hero", "landing-page",
    "pagination", "popup", "post-grid", "post-loop", "post-section", "pricing",
    "product-categories", "product-tabs", "products", "pros-and-cons",
    "single-post", "single-product", "slider", "table-of-contents", "team",
    "template-kits", "testimonials",
}


def parse_bricks_payload(text: str) -> dict[str, Any] | None:
    """Devuelve el dict si `text` es un JSON Bricks copy/paste válido.

    Reconocido por la presencia de `source == bricksCopiedElements` y
    `content` como lista.
    """
    if not text or BRICKS_SOURCE_MARKER not in text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("source") != BRICKS_SOURCE_MARKER:
        return None
    if not isinstance(data.get("content"), list):
        return None
    return data


def slugify(label: str) -> str:
    """Convierte 'Footer 2' → 'footer-2'."""
    s = label.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def content_digest(content: list[dict[str, Any]]) -> str:
    """SHA256 del content (sort_keys) para dedup."""
    payload = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def detect_snake_case_settings(content: list[dict[str, Any]]) -> list[str]:
    """Devuelve lista de keys mal-tipadas detectadas (informativo).
    Brickstemplate exporta shape correcto — esto es defensivo."""
    bad: list[str] = []
    for el in content:
        if not isinstance(el, dict):
            continue
        settings = el.get("settings") or {}
        typo = settings.get("_typography") or {}
        for k in typo:
            if "_" in k and k != "color":
                bad.append(f"{el.get('name','?')}.{k}")
    return bad


def find_unique_slug(category_dir: Path, base_slug: str) -> str:
    """Si `base_slug.json` existe, prueba `base_slug-2.json`, etc."""
    candidate = category_dir / f"{base_slug}.json"
    if not candidate.exists():
        return base_slug
    n = 2
    while (category_dir / f"{base_slug}-{n}.json").exists():
        n += 1
    return f"{base_slug}-{n}"


def load_index() -> list[dict[str, Any]]:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARN: {INDEX_PATH} corrupto — se reescribirá.", file=sys.stderr)
    return []


def save_index(entries: list[dict[str, Any]]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_index_entry(
    category: str,
    slug: str,
    label: str,
    payload: dict[str, Any],
    digest: str,
) -> dict[str, Any]:
    content = payload["content"]
    global_classes = payload.get("globalClasses") or []
    has_image = any(
        el.get("name") in {"image", "image-gallery", "logo"} or
        (el.get("settings") or {}).get("_background", {}).get("image")
        for el in content if isinstance(el, dict)
    )
    has_cta = any(el.get("name") == "button" for el in content if isinstance(el, dict))
    return {
        "slug": slug,
        "category": category,
        "label": label,
        "file": f"{category}/{slug}.json",
        "n_elements": len(content),
        "n_global_classes": len(global_classes),
        "has_image": has_image,
        "has_cta": has_cta,
        "source_url": payload.get("sourceUrl", ""),
        "bricks_version": payload.get("version", ""),
        "content_sha": digest,
    }


def save_template(
    category: str,
    payload: dict[str, Any],
    index: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    """Persiste el template y actualiza el índice.

    Devuelve `(slug, status, was_duplicate)` donde status es 'saved' | 'duplicate'.
    """
    digest = content_digest(payload["content"])
    for entry in index:
        if entry["content_sha"] == digest:
            return entry["slug"], "duplicate", True

    label = ""
    for el in payload["content"]:
        if isinstance(el, dict) and el.get("label"):
            label = el["label"]
            break
    if not label:
        label = f"untitled-{digest[:6]}"

    base_slug = slugify(label)
    category_dir = CATALOG_ROOT / category
    category_dir.mkdir(parents=True, exist_ok=True)
    slug = find_unique_slug(category_dir, base_slug)

    file_path = category_dir / f"{slug}.json"
    file_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    index.append(build_index_entry(category, slug, label, payload, digest))
    save_index(index)
    return slug, "saved", False


def main() -> int:
    if pyperclip is None:
        print(
            "ERROR: pyperclip no instalado. Ejecuta:\n"
            "  pip install pyperclip",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category", required=True,
        help=f"Categoría activa. Conocidas: {sorted(KNOWN_CATEGORIES)}",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=0.5,
        help="Segundos entre lecturas del clipboard (default 0.5)",
    )
    args = parser.parse_args()

    category = args.category.strip().lower()
    if category not in KNOWN_CATEGORIES:
        print(
            f"WARN: '{category}' no está en categorías conocidas — usaré igual.",
            file=sys.stderr,
        )

    CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    index = load_index()
    by_category = {c: sum(1 for e in index if e["category"] == c) for c in {e["category"] for e in index}}

    print(f"=== brickstemplate clipboard listener ===")
    print(f"Categoría activa: {category}")
    print(f"Output: {CATALOG_ROOT / category}/")
    print(f"Estado actual: {len(index)} templates total — {by_category.get(category, 0)} en '{category}'")
    print(f"Workflow: copia un template desde su web. El script lo detecta y guarda.")
    print(f"Para cambiar categoría: Ctrl+C y relanza con --category <otra>")
    print(f"---")

    last_seen = ""
    count_session = 0
    try:
        while True:
            current = pyperclip.paste()
            if current and current != last_seen:
                last_seen = current
                payload = parse_bricks_payload(current)
                if payload is None:
                    continue
                bad_keys = detect_snake_case_settings(payload["content"])
                slug, status, was_dup = save_template(category, payload, index)
                count_session += 1
                if status == "saved":
                    entry = next(e for e in index if e["slug"] == slug and e["category"] == category)
                    flags = []
                    if entry["has_image"]:
                        flags.append("img")
                    if entry["has_cta"]:
                        flags.append("cta")
                    flag_str = f" [{','.join(flags)}]" if flags else ""
                    print(
                        f"✓ [#{count_session} this session, {len(index)} total] "
                        f"{slug} ({entry['n_elements']} els, "
                        f"{entry['n_global_classes']} classes){flag_str}"
                    )
                    if bad_keys:
                        print(f"  ⚠️  snake_case detectado: {bad_keys[:3]}")
                else:
                    print(f"⊘ duplicado de '{slug}' — skip")
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print(f"\n[Stop] {count_session} guardados en esta sesión. {len(index)} total.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
