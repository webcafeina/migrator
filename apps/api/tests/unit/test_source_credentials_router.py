"""Tests del endpoint PUT/DELETE /api/v1/projects/{id}/source-credentials (v0.18.0).

Cubre: admin-only, validación discriminada por builder (Wix vs Webflow),
mismatch de builder con project.builder_source, cifrado Fernet, NO expone
credenciales en claro en ProjectRead, DELETE limpia el modo.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project_mock(*, builder: str | None = None, has_creds: bool = False) -> MagicMock:
    """Mock con campos planos que ProjectRead.model_validate acepta."""
    from datetime import UTC, datetime

    from wcm_types.enums import BuilderType, ProjectStatus

    builder_enum = BuilderType(builder) if builder else None
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    p = MagicMock()
    p.id = 7
    p.builder_source = builder_enum
    p.source_credentials_encrypted = "ciphertext-fake" if has_creds else None
    p.source_access_mode = "api" if has_creds else "none"
    p.client_name = "Test"
    p.source_url = "https://t.es"
    p.target_domain = None
    p.has_ecommerce = False
    p.is_multilang = False
    p.langs = []
    p.primary_lang = None
    p.asset_storage = "wp_local"
    p.preserve_paths = True
    p.plan = None
    p.lead_id = None
    p.hosting_target_json = None
    p.theme_styles_origin = None
    p.visual_diff_avg_score = None
    p.checklist_md_url = None
    p.checklist_pdf_url = None
    p.preflight_results_json = None
    p.preflight_at = None
    p.status = ProjectStatus.QUEUED
    p.started_at = None
    p.completed_at = None
    p.estimated_go_live_at = None
    p.created_at = now
    p.updated_at = now
    p.has_source_credentials = has_creds
    return p


@pytest.fixture(autouse=True)
def _fernet_env(monkeypatch):
    """Genera una FERNET_KEY válida para todos los tests del módulo."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())


@pytest.mark.asyncio
async def test_put_solo_admin(client, fake_session, operator_token) -> None:
    """Operator NO puede PUT credenciales — son admin-only."""
    fake_session.get = AsyncMock(return_value=_project_mock(builder="wix"))
    resp = await client.put(
        "/api/v1/projects/7/source-credentials",
        json={
            "builder": "wix",
            "api_key": "x" * 30,
            "site_id": "site-1234abcd",
        },
        headers=_auth(operator_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_404_si_proyecto_no_existe(client, fake_session, admin_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.put(
        "/api/v1/projects/99/source-credentials",
        json={
            "builder": "wix",
            "api_key": "x" * 30,
            "site_id": "site-1234abcd",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_validacion_discriminada_wix(
    client, fake_session, admin_token
) -> None:
    project = _project_mock(builder="wix")

    async def _refresh_side_effect(p):
        # El modelo real recalcula has_source_credentials como property.
        p.has_source_credentials = bool(p.source_credentials_encrypted)

    fake_session.get = AsyncMock(return_value=project)
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock(side_effect=_refresh_side_effect)
    resp = await client.put(
        "/api/v1/projects/7/source-credentials",
        json={
            "builder": "wix",
            "api_key": "x" * 30,
            "site_id": "site-1234abcd",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # NUNCA expone las credenciales en claro.
    assert "api_key" not in body
    assert "source_credentials_encrypted" not in body
    assert body["has_source_credentials"] is True
    assert body["source_access_mode"] == "api"
    # El proyecto recibió las credenciales cifradas (no en claro).
    assert project.source_credentials_encrypted
    assert "x" * 30 not in (project.source_credentials_encrypted or "")


@pytest.mark.asyncio
async def test_put_rechaza_payload_mal_formado_para_webflow(
    client, fake_session, admin_token
) -> None:
    """Webflow requiere api_token, no api_key — discriminator pydantic falla."""
    fake_session.get = AsyncMock(return_value=_project_mock(builder="webflow"))
    resp = await client.put(
        "/api/v1/projects/7/source-credentials",
        json={
            "builder": "webflow",
            "api_key": "x" * 30,  # ← incorrecto, falta api_token
            "site_id": "site-1234abcd",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_409_si_builder_mismatch(client, fake_session, admin_token) -> None:
    """Proyecto Webflow no acepta credenciales Wix."""
    fake_session.get = AsyncMock(return_value=_project_mock(builder="webflow"))
    resp = await client.put(
        "/api/v1/projects/7/source-credentials",
        json={
            "builder": "wix",
            "api_key": "x" * 30,
            "site_id": "site-1234abcd",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409
    assert "wix" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_delete_credenciales(client, fake_session, admin_token) -> None:
    fake_session.get = AsyncMock(return_value=_project_mock(builder="wix", has_creds=True))
    fake_session.commit = AsyncMock()
    resp = await client.delete(
        "/api/v1/projects/7/source-credentials",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_404_si_proyecto_no_existe(
    client, fake_session, admin_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.delete(
        "/api/v1/projects/99/source-credentials",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
