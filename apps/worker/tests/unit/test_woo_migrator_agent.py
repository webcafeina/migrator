"""Tests del WooMigratorAgent (v0.17.0).

Mockean el cliente WP REST (`WpRestClient` async context manager) y la
DB session. Verifican los 4 caminos del agent:

1. Project sin has_ecommerce → fase saltada sin tocar nada.
2. WooCommerce no detectado en destino → residual + SKIPPED.
3. Sin productos en woo_products → residual + SKIPPED.
4. Happy path: productos migrados, categorías upserted, residual de
   pasarela de pago siempre presente.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.woo_migrator import WooMigratorAgent, _woocommerce_available
from wcm_worker.errors import WooMigratorError
from wcm_wp_client.errors import WpNotFoundError


def _project_mock(*, has_ecommerce: bool = True) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.has_ecommerce = has_ecommerce
    p.client_name = "Tienda Pepe"
    return p


def _product_mock(
    *, sku: str = "SKU-001", name: str = "Producto Test", price: float | None = 19.99
) -> MagicMock:
    """`WooProduct` mockeado con los campos que toca el agent."""
    p = MagicMock()
    p.sku = sku
    p.name = name
    p.price = Decimal(str(price)) if price is not None else None
    p.stock = None
    p.stock_managed = False
    p.categories = []
    p.image_asset_ids = []
    p.wp_product_id = None
    return p


def _fake_wp_config() -> MagicMock:
    cfg = MagicMock()
    cfg.site_url = "https://destino.test"
    return cfg


@asynccontextmanager
async def _fake_rest_ctx(client: AsyncMock):
    """Helper para reemplazar `async with WpRestClient(cfg) as rest`."""
    yield client


def _patch_rest_client(client: AsyncMock):
    """Devuelve un patch que sustituye `WpRestClient(cfg)` por nuestro mock."""
    factory = MagicMock(return_value=_fake_rest_ctx(client))
    return patch("wcm_worker.agents.woo_migrator.WpRestClient", factory)


def test_agent_requires_project_id(fake_session) -> None:
    with pytest.raises(WooMigratorError, match="project_id"):
        WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session)
        )


def test_agent_project_not_found(fake_session) -> None:
    fake_session.get.return_value = None
    with pytest.raises(WooMigratorError, match="no encontrado"):
        WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=99)
        )


def test_agent_has_ecommerce_false_salta(fake_session) -> None:
    fake_session.get.return_value = _project_mock(has_ecommerce=False)
    result = WooMigratorAgent(wp_config=_fake_wp_config()).run(
        AgentContext(session=fake_session, project_id=7)
    )
    assert "saltada" in result.summary
    assert result.residual_tasks_created == 0
    # NO se llamó a session.add (sin residuals).
    fake_session.add.assert_not_called()


def test_woocommerce_no_disponible_crea_residual_y_skippea(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result

    rest = AsyncMock()
    rest._request = AsyncMock(
        side_effect=WpNotFoundError("404", status_code=404, body="")
    )

    with _patch_rest_client(rest):
        result = WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert "NO instalado" in result.summary
    assert result.outputs["woocommerce_available"] is False
    assert result.residual_tasks_created == 1
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert len(residuals) == 1
    assert "WooCommerce" in residuals[0].title


def test_sin_productos_crea_residual_y_skippea(fake_session) -> None:
    fake_session.get.return_value = _project_mock()
    empty_result = MagicMock()
    empty_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    fake_session.execute.return_value = empty_result

    rest = AsyncMock()
    # WC disponible (system_status responde OK).
    fake_resp = MagicMock()
    fake_resp.json = MagicMock(return_value=[])
    rest._request = AsyncMock(return_value=fake_resp)

    with _patch_rest_client(rest):
        result = WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["woocommerce_available"] is True
    assert result.outputs["products_migrated"] == 0
    assert result.residual_tasks_created == 1
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert any("manualmente" in r.title for r in residuals)


def test_happy_path_migra_productos_y_crea_residual_pasarela(fake_session) -> None:
    """Con WC + 2 productos, hace 1 GET WC + 1 GET por SKU + 1 POST por producto + categorías."""
    fake_session.get.return_value = _project_mock()
    products = [
        _product_mock(sku="SKU-001", name="Producto A"),
        _product_mock(sku="SKU-002", name="Producto B"),
    ]
    products_result = MagicMock()
    products_result.scalars = MagicMock(return_value=MagicMock(all=lambda: products))
    fake_session.execute.return_value = products_result

    rest = AsyncMock()
    calls: list[tuple[str, str]] = []

    async def _fake_request(method: str, path: str, **kw):
        calls.append((method, path))
        resp = MagicMock()
        if path == "/wc/v3/system_status/tools":
            resp.json = MagicMock(return_value=[])
            return resp
        if path == "/wc/v3/products" and method == "GET":
            # Producto no existe aún (lista vacía).
            resp.json = MagicMock(return_value=[])
            return resp
        if path == "/wc/v3/products" and method == "POST":
            resp.json = MagicMock(return_value={"id": 555})
            return resp
        resp.json = MagicMock(return_value=[])
        return resp

    rest._request = _fake_request

    with _patch_rest_client(rest):
        result = WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["products_migrated"] == 2
    assert result.outputs["products_failed"] == 0
    # 1 residual de pasarela.
    added = [c.args[0] for c in fake_session.add.call_args_list]
    residuals = [o for o in added if type(o).__name__ == "ResidualTask"]
    assert any("pasarela" in r.title.lower() for r in residuals)
    # wp_product_id se asignó.
    assert all(p.wp_product_id == 555 for p in products)


def test_producto_fallido_no_para_la_migracion(fake_session) -> None:
    """Si un producto lanza durante upsert, el siguiente sigue."""
    fake_session.get.return_value = _project_mock()
    products = [
        _product_mock(sku="SKU-FAIL"),
        _product_mock(sku="SKU-OK"),
    ]
    products_result = MagicMock()
    products_result.scalars = MagicMock(return_value=MagicMock(all=lambda: products))
    fake_session.execute.return_value = products_result

    rest = AsyncMock()
    call_count = {"n": 0}

    async def _fake_request(method: str, path: str, **kw):
        resp = MagicMock()
        if path == "/wc/v3/system_status/tools":
            resp.json = MagicMock(return_value=[])
            return resp
        if path == "/wc/v3/products" and method == "GET":
            call_count["n"] += 1
            # Primer producto: simular falla.
            if call_count["n"] == 1:
                raise RuntimeError("network blip")
            resp.json = MagicMock(return_value=[])
            return resp
        if path == "/wc/v3/products" and method == "POST":
            resp.json = MagicMock(return_value={"id": 777})
            return resp
        resp.json = MagicMock(return_value=[])
        return resp

    rest._request = _fake_request

    with _patch_rest_client(rest):
        result = WooMigratorAgent(wp_config=_fake_wp_config()).run(
            AgentContext(session=fake_session, project_id=7)
        )

    assert result.outputs["products_migrated"] == 1
    assert result.outputs["products_failed"] == 1
    assert any("SKU-FAIL" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_helper_woocommerce_available_404_es_false() -> None:
    rest = AsyncMock()
    rest._request = AsyncMock(
        side_effect=WpNotFoundError("404", status_code=404, body="")
    )
    assert await _woocommerce_available(rest) is False


@pytest.mark.asyncio
async def test_helper_woocommerce_available_200_es_true() -> None:
    rest = AsyncMock()
    rest._request = AsyncMock(return_value=MagicMock())
    assert await _woocommerce_available(rest) is True


def test_config_env_incompleta_propaga_error(fake_session) -> None:
    """Sin `wp_config` inyectado y .env vacío → WooMigratorError claro."""
    fake_session.get.return_value = _project_mock()
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(WooMigratorError, match="Config WP destino"),
    ):
        WooMigratorAgent().run(
            AgentContext(session=fake_session, project_id=7)
        )
