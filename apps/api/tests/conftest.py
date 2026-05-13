"""Fixtures comunes para tests del API.

Estrategia: dependency override de `get_session` y `get_settings`. Sin
Postgres real, sin Redis real, sin Celery worker real. Cada test
configura los mocks que necesita.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def _ensure_test_env() -> None:
    """Sobreescribe env vars para que `ApiSettings` arranque en tests
    sin depender del .env real del repo."""
    defaults = {
        "ENV": "development",
        "SECRET_KEY": "test-secret-not-real-just-for-tests",
        "JWT_SECRET": "test-jwt-secret-not-real-1234567890",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_wcm",
        "DATABASE_SYNC_URL": "postgresql://test:test@localhost:5432/test_wcm",
        "REDIS_URL": "redis://localhost:6379/15",
        "CELERY_BROKER_URL": "redis://localhost:6379/15",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/15",
        "SESSION_COOKIE_NAME": "wcm_session",
        "CORS_ORIGINS": "http://localhost:3000",
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)


_ensure_test_env()


@pytest.fixture()
def fake_session() -> MagicMock:
    """AsyncSession mockeada. Tests configuran `execute`, `get`, etc.
    según necesiten.
    """
    session = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture()
def app(fake_session: MagicMock):
    """App FastAPI con `get_session` overrideado para devolver el mock."""
    # Importar tras setear env vars
    from wcm_api.db import get_session
    from wcm_api.main import create_app

    application = create_app()

    async def _override_get_session() -> AsyncIterator[MagicMock]:
        yield fake_session

    application.dependency_overrides[get_session] = _override_get_session
    return application


@pytest.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient apuntado al ASGI app — sin red real."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
def admin_token() -> str:
    from wcm_api.security import issue_session_token

    token, _ = issue_session_token(user_id=uuid.uuid4(), role="admin")
    return token


@pytest.fixture()
def operator_token() -> str:
    from wcm_api.security import issue_session_token

    token, _ = issue_session_token(user_id=uuid.uuid4(), role="operator")
    return token


@pytest.fixture()
def viewer_token() -> str:
    from wcm_api.security import issue_session_token

    token, _ = issue_session_token(user_id=uuid.uuid4(), role="viewer")
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
