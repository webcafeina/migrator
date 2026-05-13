"""Fixtures comunes para tests del worker."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


def _ensure_env() -> None:
    os.environ.setdefault("DATABASE_SYNC_URL", "postgresql://test:test@localhost:5432/test_wcm")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/15")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/15")
    os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")


_ensure_env()


@pytest.fixture()
def fake_session() -> MagicMock:
    """Session SQLAlchemy mockeada con métodos sync (Session, no AsyncSession)."""
    session = MagicMock()
    session.execute = MagicMock()
    session.get = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = MagicMock()
    session.close = MagicMock()
    return session
