"""Tests ADR-045 — Webflow list_orders + list_coupons."""

from __future__ import annotations

import httpx
import pytest
import respx

from wcm_worker.integrations.webflow_api import WebflowApiClient


@pytest.mark.asyncio
async def test_list_orders_mapea_shape_webflow_a_woo_schema() -> None:
    sample = {
        "orders": [
            {
                "orderId": "wf-order-1",
                "orderNumber": "100043",
                "status": "fulfilled",
                "paymentProcessed": True,
                "currency": "EUR",
                "totals": {"total": 49.9},
                "customerInfo": {
                    "email": "buyer@example.com",
                    "fullName": "John Doe",
                },
                "billingAddress": {"line1": "Av. Castellana 1"},
                "shippingAddress": {"line1": "Av. Castellana 2"},
                "purchasedItems": [{"productId": "p1", "qty": 1}],
                "acceptedOn": "2026-05-15T09:00:00Z",
                "paymentMethod": "stripe",
            }
        ]
    }
    async with respx.mock(base_url="https://api.webflow.com/v2") as mock:
        mock.get("/sites/site-abc-1234/orders").mock(
            return_value=httpx.Response(200, json=sample)
        )
        async with WebflowApiClient(
            api_token="t" * 30, site_id="site-abc-1234"
        ) as client:
            orders = await client.list_orders()

    assert len(orders) == 1
    o = orders[0]
    assert o["external_id"] == "wf-order-1"
    assert o["order_number"] == "100043"
    assert o["financial_status"] == "paid"
    assert o["customer_email"] == "buyer@example.com"
    assert o["customer_name"] == "John Doe"
    assert o["billing_address"] == {"line1": "Av. Castellana 1"}


@pytest.mark.asyncio
async def test_list_coupons_devuelve_lista() -> None:
    sample = {
        "promoCodes": [
            {"id": "pc1", "code": "WELCOME10", "discountType": "percent"}
        ]
    }
    async with respx.mock(base_url="https://api.webflow.com/v2") as mock:
        mock.get("/sites/site-abc-1234/promo_codes").mock(
            return_value=httpx.Response(200, json=sample)
        )
        async with WebflowApiClient(
            api_token="t" * 30, site_id="site-abc-1234"
        ) as client:
            coupons = await client.list_coupons()
    assert coupons == sample["promoCodes"]
