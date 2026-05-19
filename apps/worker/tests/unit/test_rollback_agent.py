"""Tests del RollbackAgent (v0.19.0).

Cubre los caminos:
- Sin project_id → error.
- Project no existe → error.
- Sin páginas con wp_post_id → fase saltada limpia.
- Happy path: borra todas las páginas vía REST DELETE force=true.
- Página individual falla → continúa con la siguiente.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.rollback import RollbackAgent
from wcm_worker.errors import RollbackAgentError


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
    return patch("wcm_worker.agents.rollback.WpRestClient", factory)


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(RollbackAgentError, match="project_id"):
        RollbackAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session)
        )


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(RollbackAgentError, match="no encontrado"):
        RollbackAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=99)
        )


def test_sin_paginas_skippea_sin_tocar_rest(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    empty = MagicMock()
    empty.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty

    with patch("wcm_worker.agents.rollback.WpRestClient") as wpr:
        result = RollbackAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )
        wpr.assert_not_called()

    assert result.outputs["pages_deleted"] == 0
    assert "nada que deshacer" in result.summary


def test_happy_path_borra_todas_las_paginas(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    pages = [_page_mock(11, "home"), _page_mock(22, "contacto")]
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = result_mock

    rest = AsyncMock()
    rest.delete_page = AsyncMock(return_value={"deleted": True})

    with _patch_rest_client(rest):
        result = RollbackAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["pages_deleted"] == 2
    assert result.outputs["pages_failed"] == 0
    assert rest.delete_page.await_count == 2
    # wp_post_id se reseteó a None en ambas páginas.
    assert pages[0].wp_post_id is None
    assert pages[1].wp_post_id is None


def test_pagina_individual_falla_no_para_rollback(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    pages = [_page_mock(11), _page_mock(22)]
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock(all=lambda: pages))
    fake_session.execute.return_value = result_mock

    rest = AsyncMock()
    call_count = {"n": 0}

    async def _fake_delete(post_id, force=True):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("temporary network blip")
        return {"deleted": True}

    rest.delete_page = AsyncMock(side_effect=_fake_delete)

    with _patch_rest_client(rest):
        result = RollbackAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["pages_deleted"] == 1
    assert result.outputs["pages_failed"] == 1
    assert len(result.warnings) == 1
    # La página fallida mantiene wp_post_id, la OK lo resetea.
    assert pages[0].wp_post_id == 11
    assert pages[1].wp_post_id is None
