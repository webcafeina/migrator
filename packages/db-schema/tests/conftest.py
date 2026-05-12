"""Fixtures comunes de tests para wcm_db.

Estrategia de testing:
- **Sin BD**: la mayoría de tests validan importación de modelos, consistencia
  de enums, valores por defecto y signatures de relaciones — no requieren DB.
- **Postgres real**: para tests del schema completo (incluido pgvector,
  ARRAY, JSONB, UUID, índice ivfflat) se marca con `@pytest.mark.postgres`.
  Si `DATABASE_SYNC_URL` no apunta a Postgres, se skippean automáticamente.

No usamos SQLite como fallback genérico porque los tipos Postgres-específicos
(Vector, ARRAY, JSONB, UUID) requieren parches que falsean la realidad. Es
preferible un test corto y honesto que un test que parece pasar pero valida
otra cosa.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine


def _postgres_url() -> str | None:
    url = os.environ.get("DATABASE_SYNC_URL")
    if url and url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        return url
    return None


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[sa.Engine]:
    """Engine Postgres real con pgvector. Skippea si no está disponible."""
    url = _postgres_url()
    if url is None:
        pytest.skip("DATABASE_SYNC_URL no apunta a Postgres; tests Postgres skippeados")
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Postgres no alcanzable: {e}")
    yield engine
    engine.dispose()
