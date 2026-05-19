"""Tests del PublishAgent (ADR-039, v0.20.0+)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.publish import PublishAgent, PublishAgentError


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    return p


def _page_mock(wp_post_id: int | None, slug: str = "home") -> MagicMock:
    bp = MagicMock()
    bp.wp_post_id = wp_post_id
    bp.slug = slug
    return bp


def _fake_wp_config() -> MagicMock:
    cfg = MagicMock()
    cfg.site_url = "https://destino.test"
    return cfg


@asynccontextmanager
async def _fake_rest_ctx(client: AsyncMock):
    yield client


def _patch_rest_client(client: AsyncMock):
    factory = MagicMock(return_value=_fake_rest_ctx(client))
    return patch("wcm_worker.agents.publish.WpRestClient", factory)


def test_requires_project_id(fake_session) -> None:
    with pytest.raises(PublishAgentError, match="project_id"):
        PublishAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session)
        )


def test_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(PublishAgentError, match="no encontrado"):
        PublishAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=99)
        )


def test_sin_paginas_devuelve_warning(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    empty = MagicMock()
    empty.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty

    with patch("wcm_worker.agents.publish.WpRestClient") as wpr:
        result = PublishAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )
        wpr.assert_not_called()

    assert result.outputs["pages_published"] == 0
    assert any("bricks_pages vacío" in w for w in result.warnings)


def test_happy_path_publica_todas(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    pages = [_page_mock(11, "home"), _page_mock(22, "contacto")]
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = result_mock

    rest = AsyncMock()
    rest.update_page = AsyncMock(return_value={"id": 11, "status": "publish"})

    with _patch_rest_client(rest):
        result = PublishAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["pages_published"] == 2
    assert result.outputs["pages_failed"] == 0
    assert rest.update_page.await_count == 2
    # Verifica que se pasó {"status": "publish"} en cada llamada.
    for call in rest.update_page.await_args_list:
        assert call.args[1] == {"status": "publish"}


def test_pagina_individual_falla_continua(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    pages = [_page_mock(11), _page_mock(22)]
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = result_mock

    rest = AsyncMock()
    count = {"n": 0}

    async def _fake_update(post_id, payload):
        count["n"] += 1
        if count["n"] == 1:
            raise RuntimeError("temporary blip")
        return {"id": post_id, "status": "publish"}

    rest.update_page = AsyncMock(side_effect=_fake_update)

    with _patch_rest_client(rest):
        result = PublishAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["pages_published"] == 1
    assert result.outputs["pages_failed"] == 1
    assert len(result.warnings) == 1
