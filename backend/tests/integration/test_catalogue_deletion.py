"""Deleting a catalogue item takes its rate history with it.

A tangible's master rates and the rate revisions logged against it describe
that tangible and nothing else. Leaving them behind after the item is deleted
produces orphaned price history that no screen can explain, so the delete is
offered as a cascade — but only after the caller has been told, in numbers,
exactly what will disappear.
"""

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


@pytest.fixture
def priced_tangible(client: TestClient) -> dict[str, Any]:
    headers = auth_headers(client)

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = client.post(url, json=payload, headers=headers)
        assert response.status_code in (200, 201), response.text
        return response.json()

    currency = post("/api/v1/master-data/currencies", {"code": "USD", "name": "US Dollar"})
    unit = post("/api/v1/master-data/units", {"code": "EA", "name": "Each"})
    vendor = post("/api/v1/master-data/vendors", {"code": "SLB", "name": "Schlumberger"})
    tangible = post(
        "/api/v1/master-data/tangibles", {"code": "BIT-1225", "name": '12-1/4" PDC Bit'}
    )
    price = post(
        "/api/v1/procurement/item-prices",
        {
            "item_id": tangible["id"],
            "vendor_id": vendor["id"],
            "currency_id": currency["id"],
            "unit_id": unit["id"],
            "unit_price": "25000",
            "effective_from": "2026-01-01",
        },
    )
    post(
        f"/api/v1/procurement/item-prices/{price['id']}/revise",
        {"unit_price": "27500", "effective_from": "2026-07-01", "change_reason": "Annual review"},
    )
    return {"headers": headers, "tangible": tangible}


def test_delete_impact_reports_the_rate_history_at_risk(
    client: TestClient, priced_tangible: dict[str, Any]
) -> None:
    """The caution prompt is driven by real counts, not a generic warning."""

    tangible_id = priced_tangible["tangible"]["id"]

    response = client.get(
        f"/api/v1/master-data/tangibles/{tangible_id}/delete-impact",
        headers=priced_tangible["headers"],
    )

    body = response.json()
    assert body["requires_confirmation"] is True
    cascades = {entry["entity"]: entry["count"] for entry in body["cascades"]}
    assert cascades["item-prices"] == 2
    assert cascades["rate-revisions"] == 2


def test_deleting_a_tangible_removes_its_rate_revisions(
    client: TestClient, priced_tangible: dict[str, Any]
) -> None:
    headers = priced_tangible["headers"]
    tangible_id = priced_tangible["tangible"]["id"]

    deleted = client.delete(
        f"/api/v1/master-data/tangibles/{tangible_id}?hard=true&cascade=true", headers=headers
    )

    assert deleted.status_code == 204
    assert client.get("/api/v1/procurement/rate-revisions", headers=headers).json()["total"] == 0
    assert client.get("/api/v1/procurement/item-prices", headers=headers).json()["total"] == 0
    assert (
        client.get(f"/api/v1/master-data/tangibles/{tangible_id}", headers=headers).status_code
        == 404
    )


def test_deleting_without_cascade_is_refused_while_rates_exist(
    client: TestClient, priced_tangible: dict[str, Any]
) -> None:
    """Without the confirmed cascade the rate history still protects the item."""

    response = client.delete(
        f"/api/v1/master-data/tangibles/{priced_tangible['tangible']['id']}?hard=true",
        headers=priced_tangible["headers"],
    )

    assert response.status_code == 409


def test_unified_catalogue_entity_creates_typed_items(client: TestClient) -> None:
    """One catalogue register serves every item type, chosen by ``item_type``."""

    headers = auth_headers(client)

    created = client.post(
        "/api/v1/master-data/catalog-items",
        json={"code": "MWD", "name": "MWD Service", "item_type": "service"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["item_type"] == "service"

    listed = client.get("/api/v1/master-data/catalog-items?item_type=service", headers=headers)
    assert [item["code"] for item in listed.json()["items"]] == ["MWD"]

    retyped = client.patch(
        f"/api/v1/master-data/catalog-items/{created.json()['id']}",
        json={"item_type": "tangible"},
        headers=headers,
    )
    assert retyped.status_code == 422
    assert "cannot be changed" in retyped.json()["error"]["message"]
