"""Validación básica: todos los modelos cargan sin error y la metadata
contiene exactamente las tablas esperadas.
"""

from __future__ import annotations

from wcm_db import Base
from wcm_db import models as wcm_models

EXPECTED_TABLES = {
    "users",
    "leads",
    "lead_enrichments",
    "opt_out_log",
    "outreach_sequences",
    "outreach_sends",
    "projects",
    "project_phases",
    "scraped_pages",
    "assets",
    "content_blocks",
    "bricks_pages",
    "woo_products",
    "seo_redirects",
    "residual_tasks",
    "audit_log",
    "error_log",
    "campaigns",
}


def test_metadata_contains_expected_tables() -> None:
    actual = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - actual
    extra = actual - EXPECTED_TABLES
    assert not missing, f"Faltan tablas en metadata: {missing}"
    assert not extra, f"Tablas inesperadas en metadata: {extra}"


def test_models_module_exports_all_entities() -> None:
    """Asegura que wcm_db.models re-exporta cada modelo (alembic los necesita)."""
    expected_models = {
        "Asset",
        "AuditLog",
        "BricksPage",
        "Campaign",
        "ContentBlock",
        "ErrorLog",
        "Lead",
        "LeadEnrichment",
        "OptOutLog",
        "OutreachSend",
        "OutreachSequence",
        "Project",
        "ProjectPhase",
        "ResidualTask",
        "ScrapedPage",
        "SeoRedirect",
        "User",
        "WooProduct",
    }
    actual = {name for name in dir(wcm_models) if not name.startswith("_")}
    missing = expected_models - actual
    assert not missing, f"Modelos no re-exportados: {missing}"


def test_naming_convention_applied_to_primary_keys() -> None:
    """Naming convention 'pk_<table>' debe estar aplicada en todas las tablas."""
    for table in Base.metadata.tables.values():
        pk = table.primary_key
        assert pk.name == f"pk_{table.name}", f"PK mal nombrada en {table.name}: {pk.name}"
