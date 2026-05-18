"""Tests del CRUD de plantillas de contacto (v0.12.0).

RBAC: lectura any_user, escritura admin only. Mantener `name` único.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _tpl_mock(
    *, tpl_id: int = 1, name: str = "wix_intro_es",
) -> MagicMock:
    t = MagicMock()
    t.id = tpl_id
    t.name = name
    t.subject_template = "{{ business_name }}, una idea"
    t.body_template = "Hola, soy..."
    t.language = "es"
    now = datetime.now(UTC)
    t.created_at = now
    t.updated_at = now
    return t


# ---------- LIST ----------

@pytest.mark.asyncio
async def test_list_templates_any_user_puede_leer(
    client, fake_session, viewer_token
) -> None:
    """Viewer puede listar plantillas (utilidad operativa, no sensible)."""
    result = MagicMock()
    result.scalars = MagicMock(
        return_value=MagicMock(all=lambda: [_tpl_mock(tpl_id=1), _tpl_mock(tpl_id=2, name="followup_es")])
    )
    fake_session.execute = AsyncMock(return_value=result)
    resp = await client.get(
        "/api/v1/templates", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


@pytest.mark.asyncio
async def test_list_templates_filtra_por_language(
    client, fake_session, operator_token
) -> None:
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute = AsyncMock(return_value=result)
    resp = await client.get(
        "/api/v1/templates?language=en", headers=_auth(operator_token)
    )
    assert resp.status_code == 200
    stmt = fake_session.execute.call_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "language" in sql.lower() and "'en'" in sql.lower()


# ---------- GET ----------

@pytest.mark.asyncio
async def test_get_template_404(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get(
        "/api/v1/templates/999", headers=_auth(viewer_token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_template_devuelve_shape_completa(
    client, fake_session, viewer_token
) -> None:
    fake_session.get = AsyncMock(return_value=_tpl_mock())
    resp = await client.get(
        "/api/v1/templates/1", headers=_auth(viewer_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "id", "name", "subject_template", "body_template", "language",
        "created_at", "updated_at",
    }


# ---------- CREATE ----------

@pytest.mark.asyncio
async def test_create_template_requires_admin(
    client, operator_token
) -> None:
    """Operator NO puede crear plantillas (decisión que afecta a TODOS
    los drafts futuros — admin only)."""
    resp = await client.post(
        "/api/v1/templates",
        headers=_auth(operator_token),
        json={
            "name": "nuevo_es",
            "subject_template": "Asunto",
            "body_template": "Cuerpo",
            "language": "es",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_template_admin_success_201(
    client, fake_session, admin_token
) -> None:
    fake_session.commit = AsyncMock()

    # Simula que tras refresh la BD asigna id + timestamps. El
    # endpoint instancia el modelo real (no mock), así que `refresh`
    # debe rellenar los campos auto-generados para que
    # `model_validate` no falle.
    async def _refresh(t):
        t.id = 99
        now = datetime.now(UTC)
        t.created_at = now
        t.updated_at = now

    fake_session.refresh = AsyncMock(side_effect=_refresh)
    resp = await client.post(
        "/api/v1/templates",
        headers=_auth(admin_token),
        json={
            "name": "bar_intro_es",
            "subject_template": "{{ business_name }}, propuesta web",
            "body_template": "Hola...",
            "language": "es",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 99
    assert body["name"] == "bar_intro_es"
    fake_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_template_409_si_nombre_duplicado(
    client, fake_session, admin_token
) -> None:
    """IntegrityError de UNIQUE → 409 amistoso."""
    fake_session.commit = AsyncMock(
        side_effect=IntegrityError("dup", {}, Exception("uq fail"))
    )
    fake_session.rollback = AsyncMock()
    resp = await client.post(
        "/api/v1/templates",
        headers=_auth(admin_token),
        json={
            "name": "wix_intro_es",  # ya existe
            "subject_template": "x",
            "body_template": "y",
            "language": "es",
        },
    )
    assert resp.status_code == 409
    assert "ya existe" in resp.json()["error"]["message"].lower()


# ---------- PATCH ----------

@pytest.mark.asyncio
async def test_patch_template_requires_admin(
    client, operator_token
) -> None:
    resp = await client.patch(
        "/api/v1/templates/1",
        headers=_auth(operator_token),
        json={"subject_template": "nuevo"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_template_actualiza_campos_parciales(
    client, fake_session, admin_token
) -> None:
    """Solo los campos enviados se actualizan. `name` no editable
    (no aparece en LeadTemplateUpdate); si llega se ignora vía
    `extra="forbid"` (422)."""
    t = _tpl_mock()
    fake_session.get = AsyncMock(return_value=t)
    resp = await client.patch(
        "/api/v1/templates/1",
        headers=_auth(admin_token),
        json={"subject_template": "Nuevo asunto"},
    )
    assert resp.status_code == 200
    assert t.subject_template == "Nuevo asunto"


@pytest.mark.asyncio
async def test_patch_template_rechaza_name(
    client, admin_token
) -> None:
    """`name` no está en el schema de update — extra='forbid' lanza 422."""
    resp = await client.patch(
        "/api/v1/templates/1",
        headers=_auth(admin_token),
        json={"name": "renombrado"},
    )
    assert resp.status_code == 422


# ---------- DELETE ----------

@pytest.mark.asyncio
async def test_delete_template_requires_admin(
    client, operator_token
) -> None:
    resp = await client.delete(
        "/api/v1/templates/1", headers=_auth(operator_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_admin_204(
    client, fake_session, admin_token
) -> None:
    t = _tpl_mock()
    fake_session.get = AsyncMock(return_value=t)
    resp = await client.delete(
        "/api/v1/templates/1", headers=_auth(admin_token)
    )
    assert resp.status_code == 204
    fake_session.delete.assert_called_once_with(t)
