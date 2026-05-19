"""Tests del FormsRebuilderAgent (v0.17.0).

Cubre: detección HTML5 → DetectedForm, dedupe por título, fallback
sin Gravity Forms (residual), creación happy path, mapping de tipos.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.forms_rebuilder import (
    _FIELD_TYPE_MAP,
    DetectedForm,
    FormsRebuilderAgent,
    _build_gf_payload,
    _detect_forms,
)
from wcm_worker.errors import FormsRebuilderError


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.client_name = "Asesoría XYZ"
    return p


def _page_mock(url: str, html: str) -> MagicMock:
    p = MagicMock()
    p.url = url
    p.slug = url.rsplit("/", 1)[-1]
    p.html_raw = html
    return p


def _fake_wp_config() -> MagicMock:
    cfg = MagicMock()
    cfg.site_url = "https://destino.test"
    return cfg


@asynccontextmanager
async def _fake_rest_ctx(client: AsyncMock):
    yield client


def _patch_rest_client(client: AsyncMock):
    factory = MagicMock(return_value=_fake_rest_ctx(client))
    return patch("wcm_worker.agents.forms_rebuilder.WpRestClient", factory)


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(FormsRebuilderError, match="project_id"):
        FormsRebuilderAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session)
        )


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(FormsRebuilderError, match="no encontrado"):
        FormsRebuilderAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=99)
        )


def test_sin_forms_detectados_no_toca_destino(fake_session) -> None:
    """Si scraping no tiene forms, el agent termina sin abrir conexión WP."""
    fake_session.get.return_value = _project_mock()
    pages_result = MagicMock()
    pages_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = pages_result

    # NO se debería llamar WpRestClient en absoluto.
    with patch("wcm_worker.agents.forms_rebuilder.WpRestClient") as wpr:
        result = FormsRebuilderAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )
        wpr.assert_not_called()
    assert "0 formularios" in result.summary
    assert result.outputs["forms_created"] == 0


def test_gravity_forms_no_disponible_crea_residual(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    html = """
    <html><body>
    <form name="contacto">
      <label for="nombre">Nombre</label>
      <input id="nombre" type="text" name="name" required>
      <input type="email" name="email" required>
      <textarea name="message"></textarea>
    </form>
    </body></html>
    """
    pages = [_page_mock("https://origen.test/contacto", html)]
    pages_result = MagicMock()
    pages_result.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = pages_result

    rest = AsyncMock()
    from wcm_wp_client.errors import WpNotFoundError
    rest._request = AsyncMock(
        side_effect=WpNotFoundError("404", status_code=404, body="")
    )

    with _patch_rest_client(rest):
        result = FormsRebuilderAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["gravity_forms_available"] is False
    assert result.outputs["forms_detected"] == 1
    assert result.outputs["forms_created"] == 0
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert len(residuals) == 1
    assert "Gravity Forms" in residuals[0].title


def test_happy_path_crea_form_y_residual_revision(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    html = """
    <form id="contacto">
      <input type="text" name="name" required>
      <input type="email" name="email" required>
      <input type="tel" name="phone">
      <textarea name="msg"></textarea>
    </form>
    """
    pages = [_page_mock("https://origen.test/", html)]
    pages_result = MagicMock()
    pages_result.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = pages_result

    rest = AsyncMock()
    calls: list[tuple[str, str]] = []

    async def _fake_request(method: str, path: str, **kw):
        calls.append((method, path))
        resp = MagicMock()
        if path == "/gf/v2/forms" and method == "GET":
            resp.json = MagicMock(return_value=[])
            return resp
        if path == "/gf/v2/forms" and method == "POST":
            resp.json = MagicMock(return_value={"id": "5", "title": "Contacto"})
            return resp
        resp.json = MagicMock(return_value=[])
        return resp

    rest._request = _fake_request

    with _patch_rest_client(rest):
        result = FormsRebuilderAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["forms_created"] == 1
    assert ("POST", "/gf/v2/forms") in calls
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert any("Revisar" in r.title for r in residuals)


def test_dedupe_por_titulo(fake_session) -> None:
    """Mismo form en 2 páginas → solo se cuenta 1."""
    html = """
    <form id="contacto">
      <input type="text" name="name"><input type="email" name="email">
    </form>
    """
    pages = [
        _page_mock("https://origen.test/", html),
        _page_mock("https://origen.test/about", html),
    ]
    detected = _detect_forms(pages)
    assert len(detected) == 1


def test_detect_forms_extrae_select_choices() -> None:
    html = """
    <form id="encuesta">
      <select name="sector">
        <option value="ti">TI</option>
        <option value="legal">Legal</option>
      </select>
    </form>
    """
    pages = [_page_mock("/", html)]
    detected = _detect_forms(pages)
    assert len(detected) == 1
    select_field = next(f for f in detected[0].fields if f["type"] == "select")
    values = [c["value"] for c in select_field["choices"]]
    assert values == ["ti", "legal"]


def test_detect_forms_ignora_form_sin_campos() -> None:
    html = "<form><button>Solo botón</button></form>"
    pages = [_page_mock("/", html)]
    assert _detect_forms(pages) == []


def test_field_type_map_cubre_html5_core() -> None:
    for html5 in ("text", "email", "url", "tel", "number", "date"):
        assert html5 in _FIELD_TYPE_MAP


def test_build_gf_payload_incluye_notificacion() -> None:
    form = DetectedForm(
        title="Contacto",
        source_url="https://x.es/",
        fields=[{"id": 1, "type": "text", "label": "Nombre", "isRequired": True}],
    )
    payload = _build_gf_payload(form, "ops@webcafeina.com")
    assert payload["title"] == "Contacto"
    assert payload["is_active"] == "0"
    assert payload["notifications"]["1"]["to"] == "ops@webcafeina.com"
    assert payload["fields"][0]["label"] == "Nombre"
