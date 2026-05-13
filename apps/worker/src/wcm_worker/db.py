"""DB sync para el worker.

Celery es sync por defecto. Usamos SQLAlchemy sync con `DATABASE_SYNC_URL`
en lugar de la versión async del API. La misma BD, mismo schema; solo
cambia la dialect del driver.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.environ.get("DATABASE_SYNC_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_SYNC_URL no definida. El worker requiere acceso a Postgres."
        )
    pool_size = int(os.environ.get("DATABASE_POOL_SIZE", "5"))
    max_overflow = int(os.environ.get("DATABASE_MAX_OVERFLOW", "10"))
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager con commit/rollback automáticos.

    Uso en tasks Celery:
        with session_scope() as session:
            project = session.get(Project, project_id)
            ...
            # commit automático al salir si no hubo excepción
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
