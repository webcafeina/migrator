"""Tests del router /email-layout (v0.14.0)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _layout_mock(*, html: str | None = None, css: str | None = None) -> MagicMock:
    """Mock de `EmailLayout` con todos los campos pydantic-validables."""
    m = MagicMock()
    m.id = 1
    m.layout_html = html or "<html><body>{{ content | safe }}</body></html>"
    m.layout_css = css or ""
    m.updated_by_user_id = None
    now = datetime.now(UTC)
    m.created_at = now
    m.updated_at = now
    return m


@pytest.mark.asyncio
async def test_get_email_layout_viewer_puede_leer(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=_layout_mock())
    resp = await client.get("/api/v1/email-layout", headers=_auth(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert "content" in body["layout_html"]


@pytest.mark.asyncio
async def test_get_email_layout_404_si_no_inicializado(client, fake_session, admin_token) -> None:
    """Tabla vacía (migración no aplicada) → 404 explicativo."""
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/email-layout", headers=_auth(admin_token))
    assert resp.status_code == 404
    assert "migración" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_put_email_layout_requires_admin(client, fake_session, operator_token) -> None:
    """Operadores y viewers no pueden modificar el layout maestro."""
    resp = await client.put(
        "/api/v1/email-layout",
        headers=_auth(operator_token),
        json={"layout_html": "<html></html>", "layout_css": ""},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_email_layout_admin_actualiza(client, fake_session, admin_token) -> None:
    existing = _layout_mock()
    fake_session.get = AsyncMock(return_value=existing)

    async def _refresh(layout):
        layout.updated_at = datetime.now(UTC)

    fake_session.refresh = AsyncMock(side_effect=_refresh)

    new_html = "<html><body class='wcm'><h1>{{ company_legal_name }}</h1>{{ content | safe }}</body></html>"
    resp = await client.put(
        "/api/v1/email-layout",
        headers=_auth(admin_token),
        json={"layout_html": new_html, "layout_css": "body { color: red; }"},
    )
    assert resp.status_code == 200
    assert existing.layout_html == new_html
    assert existing.layout_css == "body { color: red; }"
    # AuditLog escrito.
    assert any(type(c.args[0]).__name__ == "AuditLog" for c in fake_session.add.call_args_list)


@pytest.mark.asyncio
async def test_put_email_layout_rechaza_jinja2_sintaxis_invalida(
    client, fake_session, admin_token
) -> None:
    """{% if foo: malformado → 422 antes de tocar BD."""
    resp = await client.put(
        "/api/v1/email-layout",
        headers=_auth(admin_token),
        json={
            "layout_html": "<html>{% if foo %}sin endif</html>",
            "layout_css": "",
        },
    )
    assert resp.status_code == 422
    detail = resp.json().get("detail") or resp.json().get("error", {}).get("message", "")
    assert "jinja2" in detail.lower() or "sintaxis" in detail.lower()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_put_email_layout_layout_html_vacio_rechazado(
    client, fake_session, admin_token
) -> None:
    """min_length=1 del schema → 422 antes de tocar el endpoint."""
    resp = await client.put(
        "/api/v1/email-layout",
        headers=_auth(admin_token),
        json={"layout_html": "", "layout_css": ""},
    )
    assert resp.status_code == 422
