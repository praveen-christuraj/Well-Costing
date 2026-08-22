"""Integration tests for vendors, catalogues, orders, and master item rates."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def post(
    client: TestClient, url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code in (200, 201), response.text
    return response.json()


@pytest.fixture
def reference_data(client: TestClient) -> dict[str, Any]:
    """Create the shared currency, units, vendors, and catalogue items."""

    headers = auth_headers(client)
    currency = post(
        client, "/api/v1/master-data/currencies", {"code": "USD", "name": "US Dollar"}, headers
    )
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, headers)
    sack = post(client, "/api/v1/master-data/units", {"code": "SK", "name": "Sack"}, headers)
    third_party = post(
        client,
        "/api/v1/master-data/vendors",
        {"code": "SLB", "name": "Schlumberger", "vendor_type": "third_party"},
        headers,
    )
    inhouse = post(
        client,
        "/api/v1/master-data/vendors",
        {"code": "INH", "name": "In-house Operations", "vendor_type": "inhouse"},
        headers,
    )
    bits = post(
        client,
        "/api/v1/master-data/item-categories",
        {"code": "BITS", "name": "Drill Bits", "applies_to": "tangible"},
        headers,
    )
    service = post(
        client,
        "/api/v1/master-data/services",
        {"code": "MWD", "name": "MWD Service", "default_unit_id": day["id"]},
        headers,
    )
    tangible = post(
        client,
        "/api/v1/master-data/tangibles",
        {
            "code": "BIT-1225",
            "name": '12-1/4" PDC Bit',
            "item_category_id": bits["id"],
            "material_number": "MAT-00912",
        },
        headers,
    )
    return {
        "headers": headers,
        "currency": currency,
        "day": day,
        "sack": sack,
        "vendor": third_party,
        "inhouse": inhouse,
        "bits": bits,
        "service": service,
        "tangible": tangible,
    }


def test_vendor_classification_and_filtering(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]

    response = client.get("/api/v1/master-data/vendors?vendor_type=inhouse", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "INH"
    assert body["items"][0]["vendor_type"] == "inhouse"


def test_vendor_type_must_be_a_known_value(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    response = client.post(
        "/api/v1/master-data/vendors",
        json={"code": "BAD", "name": "Bad Vendor", "vendor_type": "partner"},
        headers=reference_data["headers"],
    )

    assert response.status_code == 422
    assert "vendor_type" in response.json()["error"]["message"]


def test_consumable_catalogues_use_distinct_item_types(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]

    mud = post(
        client,
        "/api/v1/master-data/mud-chemicals",
        {"code": "BARITE", "name": "Barite", "material_number": "MC-1001"},
        headers,
    )
    additive = post(
        client,
        "/api/v1/master-data/cement-additives",
        {"code": "RETARDER", "name": "Cement Retarder", "material_number": "CA-2002"},
        headers,
    )

    assert mud["item_type"] == "mud_chemical"
    assert additive["item_type"] == "cement_additive"
    assert client.get("/api/v1/master-data/mud-chemicals", headers=headers).json()["total"] == 1


def test_catalogue_search_matches_material_number(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    response = client.get(
        "/api/v1/master-data/tangibles?search=MAT-009", headers=reference_data["headers"]
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_tangibles_filter_by_item_category(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    category_id = reference_data["bits"]["id"]

    response = client.get(
        f"/api/v1/master-data/tangibles?item_category_id={category_id}",
        headers=reference_data["headers"],
    )

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["item_category_code"] == "BITS"


def test_master_rates_reject_services(client: TestClient, reference_data: dict[str, Any]) -> None:
    """Services are priced per well, so master data refuses a service rate."""

    response = client.post(
        "/api/v1/procurement/item-prices",
        json={
            "item_id": reference_data["service"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "12500",
            "effective_from": "2026-01-01",
        },
        headers=reference_data["headers"],
    )

    assert response.status_code == 422
    assert "well" in response.json()["error"]["message"]


def test_effective_on_filter_excludes_out_of_window_rates(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]
    post(
        client,
        "/api/v1/procurement/item-prices",
        {
            "item_id": reference_data["tangible"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "100",
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
        },
        headers,
    )

    inside = client.get("/api/v1/procurement/item-prices?effective_on=2026-03-01", headers=headers)
    outside = client.get("/api/v1/procurement/item-prices?effective_on=2026-09-01", headers=headers)

    assert inside.json()["total"] == 1
    assert outside.json()["total"] == 0


def test_item_price_rejects_inverted_effective_dates(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    response = client.post(
        "/api/v1/procurement/item-prices",
        json={
            "item_id": reference_data["tangible"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "100",
            "effective_from": "2026-06-01",
            "effective_to": "2026-01-01",
        },
        headers=reference_data["headers"],
    )

    assert response.status_code == 422


def test_item_price_links_purchase_order_and_filters_by_item_type(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]
    purchase_order = post(
        client,
        "/api/v1/procurement/purchase-orders",
        {
            "order_number": "PO-2026-014",
            "title": "Bits and Casing",
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "order_date": "2026-02-01",
            "status": "open",
        },
        headers,
    )
    mud = post(
        client,
        "/api/v1/master-data/mud-chemicals",
        {"code": "BARITE", "name": "Barite"},
        headers,
    )
    price = post(
        client,
        "/api/v1/procurement/item-prices",
        {
            "item_id": reference_data["tangible"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "purchase_order_id": purchase_order["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "48500.00",
            "effective_from": "2026-02-01",
        },
        headers,
    )
    post(
        client,
        "/api/v1/procurement/item-prices",
        {
            "item_id": mud["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["sack"]["id"],
            "unit_price": "32.50",
            "effective_from": "2026-01-15",
        },
        headers,
    )

    assert price["purchase_order_number"] == "PO-2026-014"
    filtered = client.get("/api/v1/procurement/item-prices?item_type=mud_chemical", headers=headers)
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["item_code"] == "BARITE"


def test_bulk_create_is_all_or_nothing(client: TestClient, reference_data: dict[str, Any]) -> None:
    headers = reference_data["headers"]
    rows = [
        {
            "item_id": reference_data["tangible"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "100",
            "effective_from": "2026-01-01",
        },
        {
            "item_id": reference_data["service"]["id"],
            "vendor_id": reference_data["vendor"]["id"],
            "currency_id": reference_data["currency"]["id"],
            "unit_id": reference_data["day"]["id"],
            "unit_price": "200",
            "effective_from": "2026-01-01",
        },
    ]

    response = client.post(
        "/api/v1/procurement/item-prices/bulk/create", json={"rows": rows}, headers=headers
    )

    assert response.status_code == 422
    listed = client.get("/api/v1/procurement/item-prices", headers=headers)
    assert listed.json()["total"] == 0


def test_pagination_reports_page_count(client: TestClient, reference_data: dict[str, Any]) -> None:
    headers = reference_data["headers"]
    rows = [
        {
            "order_number": f"PO-{index:04d}",
            "title": f"Order {index}",
            "vendor_id": reference_data["vendor"]["id"],
            "order_date": "2026-02-01",
        }
        for index in range(5)
    ]
    post(client, "/api/v1/procurement/purchase-orders/bulk/create", {"rows": rows}, headers)

    response = client.get("/api/v1/procurement/purchase-orders?page=2&page_size=2", headers=headers)

    body = response.json()
    assert body["total"] == 5
    assert body["pages"] == 3
    assert body["page"] == 2
    assert len(body["items"]) == 2


def test_delete_deactivates_by_default_and_hard_delete_removes(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]
    order = post(
        client,
        "/api/v1/procurement/purchase-orders",
        {
            "order_number": "PO-DEL",
            "title": "Disposable",
            "vendor_id": reference_data["vendor"]["id"],
            "order_date": "2026-02-01",
        },
        headers,
    )

    soft = client.delete(f"/api/v1/procurement/purchase-orders/{order['id']}", headers=headers)
    assert soft.status_code == 204
    assert (
        client.get("/api/v1/procurement/purchase-orders?is_active=false", headers=headers).json()[
            "total"
        ]
        == 1
    )

    hard = client.delete(
        f"/api/v1/procurement/purchase-orders/{order['id']}?hard=true", headers=headers
    )
    assert hard.status_code == 204
    assert client.get("/api/v1/procurement/purchase-orders", headers=headers).json()["total"] == 0


def test_duplicate_order_number_conflicts(
    client: TestClient, reference_data: dict[str, Any]
) -> None:
    headers = reference_data["headers"]
    payload = {
        "order_number": "SO-DUP",
        "title": "First",
        "vendor_id": reference_data["vendor"]["id"],
        "valid_from": "2026-01-01",
    }
    post(client, "/api/v1/procurement/service-orders", payload, headers)

    response = client.post("/api/v1/procurement/service-orders", json=payload, headers=headers)

    assert response.status_code == 409
