"""Tests metadata-only de la migración 0005_email_html_layout.

Valida que la migración se puede importar, encadena correctamente con
la 0004, y declara las operaciones esperadas. Tests con Postgres real
(upgrade/downgrade ejecutados) viven en `test_postgres_schema.py` bajo
`-m postgres`; este test corre siempre en CI.
"""

from __future__ import annotations

import importlib
from pathlib import Path


def _load_migration():
    """Importa la migración 0005 directamente (vive fuera del paquete)."""
    path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0005_email_html_layout.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0005", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_id_and_chain() -> None:
    mod = _load_migration()
    assert mod.revision == "0005_email_html_layout"
    assert mod.down_revision == "0004_outreach_send_error_message"


def test_initial_layout_html_has_required_jinja_vars() -> None:
    """El layout seed debe referenciar las variables que el composer
    inyecta — si falta alguna, el render falla en runtime con
    `UndefinedError`. Aquí lo capturamos antes de mergear."""
    mod = _load_migration()
    html = mod.INITIAL_LAYOUT_HTML
    for var in (
        "{{ content | safe }}",
        "{{ logo_url }}",
        "{{ company_legal_name }}",
        "{{ company_contact_email }}",
        "{{ privacy_policy_url }}",
        "{{ opt_out_url }}",
        "{{ cta_label }}",
        "{{ cta_url }}",
    ):
        assert var in html, f"Layout seed no referencia {var}"


def test_initial_layout_css_includes_brand_palette() -> None:
    """Sanity check: el CSS contiene los hex de marca Webcafeína."""
    mod = _load_migration()
    css = mod.INITIAL_LAYOUT_CSS
    assert "#B1F100" in css, "CSS no incluye acento lima (#B1F100)"
    assert "#0E1218" in css, "CSS no incluye fondo primario (#0E1218)"


def test_upgrade_and_downgrade_callables_present() -> None:
    mod = _load_migration()
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
