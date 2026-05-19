"""Tests ADR-045 — Wix list_orders + list_coupons."""

from __future__ import annotations

import httpx
import pytest
import respx

from wcm_worker.integrations.wix_api import WixApiClient


@pytest.mark.asyncio
async def test_list_orders_mapea_shape_wix_a_woo_schema() -> None:
    sample = {
        "orders": [
            {
                "id": "order-abc-123",
                "number": "1042",
                "status": "FULFILLED",
                "paymentStatus": "PAID",
                "currency": "EUR",
                "totals": {"total": "49.90"},
                "buyerInfo": {
                    "email": "cliente@example.com",
                    "firstName": "Ana",
                    "lastName": "Pérez",
                },
                "billingInfo": {"address": {"street": "C/ Mayor 1"}},
                "shippingInfo": {
                    "shipmentDetails": {"address": {"street": "C/ Mayor 2"}}
                },
                "lineItems": [{"productId": "prod-1", "qty": 2}],
                "dateCreated": "2026-05-10T10:00:00Z",
                "paymentGatewayTransactionId": "tx-stripe-999",
            }
        ]
    }
    async with respx.mock(base_url="https://www.wixapis.com") as mock:
        mock.post("/stores/v1/orders/query").mock(
            return_value=httpx.Response(200, json=sample)
        )
        async with WixApiClient(api_key="k" * 32, site_id="site-1234abcd") as client:
            orders = await client.list_orders()

    assert len(orders) == 1
    o = orders[0]
    assert o["external_id"] == "order-abc-123"
    assert o["order_number"] == "1042"
    assert o["status"] == "FULFILLED"
    assert o["financial_status"] == "PAID"
    assert o["total_amount"] == "49.90"
    assert o["customer_email"] == "cliente@example.com"
    assert o["customer_name"] == "Ana Pérez"
    assert o["billing_address"] == {"address": {"street": "C/ Mayor 1"}}
    assert o["shipping_address"] == {"address": {"street": "C/ Mayor 2"}}
    assert o["payment_method"] == "tx-stripe-999"


@pytest.mark.asyncio
async def test_list_coupons_devuelve_lista() -> None:
    sample = {
        "coupons": [
            {"id": "c1", "code": "SUMMER20", "discountType": "PERCENTAGE"}
        ]
    }
    async with respx.mock(base_url="https://www.wixapis.com") as mock:
        mock.get("/stores/v1/coupons/query").mock(
            return_value=httpx.Response(200, json=sample)
        )
        async with WixApiClient(api_key="k" * 32, site_id="site-1234abcd") as client:
            coupons = await client.list_coupons()
    assert coupons == sample["coupons"]
