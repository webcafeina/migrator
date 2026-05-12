"""Tests del schema completo contra Postgres real con pgvector.

Skippeados si DATABASE_SYNC_URL no apunta a Postgres con la extensión
`vector` disponible. Para ejecutarlos:

    export DATABASE_SYNC_URL=postgresql://webcafeina:changeme@localhost:5432/webcafeina_migrator_test
    cd packages/db-schema
    pytest -m postgres
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from wcm_db.base import Base

pytestmark = pytest.mark.postgres


def test_pgvector_extension_available(postgres_engine: sa.Engine) -> None:
    with postgres_engine.connect() as conn:
        result = conn.execute(
            sa.text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        assert result is not None, (
            "Extensión pgvector no instalada. Aplica la migración inicial "
            "con `alembic upgrade head` o instala el plugin manualmente."
        )


def test_metadata_creates_against_postgres(postgres_engine: sa.Engine) -> None:
    """Verifica que create_all funciona en una BD Postgres real (en BD vacía).

    Usa un schema temporal para no chocar con la BD principal.
    """
    schema = "wcm_test_schema"
    with postgres_engine.connect() as conn:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(sa.text(f"CREATE SCHEMA {schema}"))
        conn.commit()

    try:
        engine_with_schema = postgres_engine.execution_options(
            schema_translate_map={None: schema}
        )
        Base.metadata.create_all(engine_with_schema)
        with engine_with_schema.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = :s"
                ),
                {"s": schema},
            ).fetchall()
            table_names = {r[0] for r in rows}
        # Subset check: si están las críticas, el create_all funcionó
        assert {"leads", "projects", "bricks_pages", "audit_log"} <= table_names
    finally:
        with postgres_engine.connect() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            conn.commit()
