"""Tests del modelo EmailLayout + columnas HTML añadidas a OutreachTemplate
y OutreachSend en v0.14.0.

Sin BD — validan la metadata SQLAlchemy directamente (la convención del
repo es minimizar dependencias de Postgres en CI; los tests con `-m
postgres` cubren la integración real).
"""

from __future__ import annotations

import sqlalchemy as sa

from wcm_db.base import Base
from wcm_db.models import EmailLayout, OutreachSend, OutreachTemplate


def test_email_layout_singleton_check_constraint_present() -> None:
    """El invariante singleton (id=1) debe estar declarado en la tabla.

    El nombre final lleva el prefijo `ck_email_layouts_` de la naming
    convention en `wcm_db.base.NAMING_CONVENTION`.
    """
    table = EmailLayout.__table__
    check_names = {c.name for c in table.constraints if isinstance(c, sa.CheckConstraint)}
    assert "ck_email_layouts_singleton" in check_names, (
        "EmailLayout debe tener CheckConstraint(name='singleton') para forzar id=1; "
        f"constraints actuales: {check_names}"
    )


def test_email_layout_columns_present_with_expected_types() -> None:
    cols = {c.name: c for c in EmailLayout.__table__.columns}
    assert set(cols) >= {
        "id",
        "layout_html",
        "layout_css",
        "updated_by_user_id",
        "created_at",
        "updated_at",
    }
    assert cols["layout_html"].nullable is False
    assert cols["layout_css"].nullable is False
    assert cols["updated_by_user_id"].nullable is True
    # id NO autoincrement (singleton; se inserta manualmente)
    assert cols["id"].autoincrement is False


def test_email_layout_fk_to_users() -> None:
    """updated_by_user_id apunta a users.id con SET NULL al borrar usuario."""
    col = EmailLayout.__table__.columns["updated_by_user_id"]
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "users"
    assert fk.column.name == "id"
    assert fk.ondelete == "SET NULL"


def test_outreach_template_html_columns_added() -> None:
    """body_html_template / cta_label / cta_url añadidos en v0.14.0."""
    cols = {c.name: c for c in OutreachTemplate.__table__.columns}
    assert "body_html_template" in cols
    assert cols["body_html_template"].nullable is True
    assert "cta_label" in cols
    assert cols["cta_label"].nullable is True
    assert "cta_url" in cols
    assert cols["cta_url"].nullable is True
    # length checks
    assert getattr(cols["cta_label"].type, "length", None) == 80
    assert getattr(cols["cta_url"].type, "length", None) == 500


def test_outreach_send_body_html_rendered_added() -> None:
    """Snapshot HTML del envío (NULL para sends pre-v0.14.0)."""
    cols = {c.name: c for c in OutreachSend.__table__.columns}
    assert "body_html_rendered" in cols
    assert cols["body_html_rendered"].nullable is True


def test_email_layouts_in_metadata() -> None:
    """La tabla debe estar registrada en Base.metadata para alembic."""
    assert "email_layouts" in Base.metadata.tables


# --- v0.15.0: theme_config column ---


def test_theme_config_column_present_as_nullable_jsonb() -> None:
    """`theme_config` añadido en migración 0006. Persiste el JSON del
    tema cuando el operador edita desde el tab Visual; NULL cuando el
    layout fue editado a mano por código."""
    cols = {c.name: c for c in EmailLayout.__table__.columns}
    assert "theme_config" in cols
    assert cols["theme_config"].nullable is True
    # Tipo JSONB (Postgres). El nombre de la clase Python varía pero
    # debe ser un tipo JSON-compatible.
    type_name = type(cols["theme_config"].type).__name__
    assert "JSON" in type_name.upper()
