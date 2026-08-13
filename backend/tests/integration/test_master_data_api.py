"""Master-data CRUD and bulk API integration tests."""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(
    client: TestClient, entity: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(f"/api/v1/master-data/{entity}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_reference_and_catalog_crud_flow(client: TestClient) -> None:
    headers = auth_headers(client)
    unit = create(client, "units", {"code": "day", "name": "Day", "symbol": "d"}, headers)
    category = create(
        client,
        "cost-categories",
        {"code": "SERV", "name": "Services"},
        headers,
    )
    cost_code = create(
        client,
        "cost-codes",
        {
            "code": "SERV-DD",
            "name": "Directional drilling",
            "cost_category_id": category["id"],
        },
        headers,
    )
    service = create(
        client,
        "services",
        {
            "code": "DD-001",
            "name": "Directional drilling service",
            "cost_category_id": category["id"],
            "cost_code_id": cost_code["id"],
            "default_unit_id": unit["id"],
        },
        headers,
    )

    listing = client.get(
        "/api/v1/master-data/services?search=directional&sort_by=name",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["cost_code"] == "SERV-DD"
    assert listing.json()["items"][0]["default_unit_code"] == "DAY"

    updated = client.patch(
        f"/api/v1/master-data/services/{service['id']}",
        json={"name": "Directional drilling and motor service"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"].endswith("motor service")
    assert updated.json()["updated_by"] is not None

    deleted = client.delete(f"/api/v1/master-data/services/{service['id']}", headers=headers)
    assert deleted.status_code == 204
    read_back = client.get(f"/api/v1/master-data/services/{service['id']}", headers=headers)
    assert read_back.json()["is_active"] is False


def test_bulk_validation_prevents_partial_commit(client: TestClient) -> None:
    headers = auth_headers(client)
    payload = {
        "rows": [
            {"code": "EA", "name": "Each"},
            {"code": "EA", "name": "Duplicate Each"},
        ]
    }
    validation = client.post(
        "/api/v1/master-data/units/bulk/validate", json=payload, headers=headers
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert validation.json()["errors"][0]["code"] == "duplicate_in_batch"

    commit = client.post("/api/v1/master-data/units/bulk/create", json=payload, headers=headers)
    assert commit.status_code == 422
    listing = client.get("/api/v1/master-data/units", headers=headers)
    assert listing.json()["total"] == 0


def test_rate_crud_references_cost_library(client: TestClient) -> None:
    headers = auth_headers(client)
    unit = create(client, "units", {"code": "HR", "name": "Hour"}, headers)
    currency = create(client, "currencies", {"code": "USD", "name": "US Dollar"}, headers)
    vendor = create(client, "vendors", {"code": "V-1", "name": "Vendor One"}, headers)
    item = create(client, "equipment", {"code": "EQ-1", "name": "Rental tool"}, headers)

    rate = client.post(
        "/api/v1/master-data/rates",
        headers=headers,
        json={
            "item_id": item["id"],
            "vendor_id": vendor["id"],
            "currency_id": currency["id"],
            "unit_id": unit["id"],
            "amount": "125.5000",
            "effective_from": "2026-01-01",
        },
    )
    assert rate.status_code == 201, rate.text
    assert rate.json()["item_code"] == "EQ-1"
    assert rate.json()["vendor_code"] == "V-1"

    invalid = client.patch(
        f"/api/v1/master-data/rates/{rate.json()['id']}",
        headers=headers,
        json={"effective_to": "2025-12-31"},
    )
    assert invalid.status_code == 422
