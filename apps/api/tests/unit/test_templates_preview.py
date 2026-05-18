"""Tests del endpoint GET /templates/{id}/preview (v0.14.0)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _tpl(*, body_html: str | None = None, cta_label: str | None = None) -> MagicMock:
    """Construye una instancia REAL de OutreachTemplate (no mock) para
    que `_render_template_with_mock_context` la trate como tal y
    acceda a los atributos sin warnings de pydantic."""
    from wcm_db.models.outreach import OutreachTemplate

    t = OutreachTemplate(
        name="wix_intro_es",
        subject_template="{{ business_name }}, una idea",
        body_template="Hola {{ business_name }}",
        language="es",
        body_html_template=body_html,
        cta_label=cta_label,
        cta_url="https://cal.com/x" if cta_label else None,
    )
    # Atributos auto-generados que el endpoint preview NO toca pero
    # `OutreachTemplateRead.model_validate` sí espera si reusamos el
    # mismo objeto.
    t.id = 1
    now = datetime.now(UTC)
    t.created_at = now
    t.updated_at = now
    return t


@pytest.mark.asyncio
async def test_preview_template_404_si_no_existe(client, fake_session, viewer_token) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.get("/api/v1/templates/99/preview", headers=_auth(viewer_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_template_con_body_html_devuelve_html_con_strong(
    client, fake_session, viewer_token
) -> None:
    tpl = _tpl(body_html="<p><strong>Hola</strong> {{ business_name }}</p>")
    # session.get se llama 2 veces: 1) OutreachTemplate, 2) EmailLayout (None → fallback)
    fake_session.get = AsyncMock(side_effect=[tpl, None])

    resp = await client.get("/api/v1/templates/1/preview", headers=_auth(viewer_token))

    assert resp.status_code == 200
    body = resp.json()
    assert "<strong>" in body["html"]
    # Demo lead se llama "Restaurante Demo" (mock_ctx en el endpoint).
    assert "Restaurante Demo" in body["html"]
    assert body["subject"] == "Restaurante Demo, una idea"


@pytest.mark.asyncio
async def test_preview_template_sin_html_usa_fallback_wrap(
    client, fake_session, viewer_token
) -> None:
    """Plantilla solo texto → composer envuelve en <p> + layout."""
    tpl = _tpl(body_html=None)
    fake_session.get = AsyncMock(side_effect=[tpl, None])

    resp = await client.get("/api/v1/templates/1/preview", headers=_auth(viewer_token))

    assert resp.status_code == 200
    html = resp.json()["html"]
    # Texto envuelto en <p> (premailer le añade `style="..."`).
    assert "<p" in html  # el wrapper
    assert "Hola Restaurante Demo" in html
    # Footer legal del layout fallback presente.
    assert "Webcafeína" in html


@pytest.mark.asyncio
async def test_preview_template_con_cta_pinta_boton(client, fake_session, viewer_token) -> None:
    tpl = _tpl(body_html="<p>Hola</p>", cta_label="Reservar 20min")
    fake_session.get = AsyncMock(side_effect=[tpl, None])

    resp = await client.get("/api/v1/templates/1/preview", headers=_auth(viewer_token))

    assert resp.status_code == 200
    html = resp.json()["html"]
    assert "Reservar 20min" in html
    assert "cal.com/x" in html
