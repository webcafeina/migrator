"""Fixtures para e2e: env vars, session mock con state interno, fixtures
HTML de muestra.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WIX_FIXTURE_PATH = (
    REPO_ROOT / "packages/scraper-core/tests/fixtures/wix/corporate.html"
)


def _ensure_env() -> None:
    defaults = {
        "DATABASE_SYNC_URL": "postgresql://test:test@localhost:5432/test_wcm",
        "CELERY_BROKER_URL": "redis://localhost:6379/15",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/15",
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "LOG_LEVEL": "warning",  # bajar ruido en e2e
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)


_ensure_env()


@pytest.fixture()
def wix_html() -> str:
    return WIX_FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def stateful_session() -> Iterator[MagicMock]:
    """Session SQLAlchemy con almacenamiento interno por tipo de entidad.

    Permite simular el ciclo `session.add(obj)` + `session.get(Model, id)`
    sin necesidad de Postgres real. `commit/flush` son no-ops.
    """
    storage: dict[str, dict[object, object]] = {}
    next_ids: dict[str, int] = {}

    def _store(obj: object) -> None:
        bucket = storage.setdefault(type(obj).__name__, {})
        if getattr(obj, "id", None) is None and hasattr(obj, "id"):
            next_ids[type(obj).__name__] = next_ids.get(type(obj).__name__, 0) + 1
            obj.id = next_ids[type(obj).__name__]
        bucket[obj.id] = obj

    def _get(model: type, id_: object) -> object | None:
        bucket = storage.get(model.__name__, {})
        return bucket.get(id_)

    session = MagicMock()
    session.add = MagicMock(side_effect=_store)
    session.add_all = MagicMock(side_effect=lambda items: [_store(i) for i in items])
    session.get = MagicMock(side_effect=_get)
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    session.refresh = MagicMock()
    # execute()/scalar_one_or_none() devuelve None por defecto — los
    # tests específicos pueden sobrescribirlo.
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalars.return_value.__iter__ = lambda s: iter([])
    session._storage = storage  # exposed para asserts
    yield session
