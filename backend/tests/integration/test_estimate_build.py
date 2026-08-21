"""Phase 4 afe-to-cost-build integration tests."""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD
from tests.integration.test_afe_api import setup_afe, setup_references


def auth(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create(
    client: TestClient, path: str, data: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(path, json=data, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def submitted_afe(
    client: TestClient, headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    refs = setup_references(client, headers)
    _, _, afe = setup_afe(client, headers)
    item = create(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 3,
            "unit_id": refs["day"]["id"],
        },
        headers,
    )
    response = client.post(f"/api/v1/afes/{afe['id']}/submit", headers=headers)
    assert response.status_code == 200
    return response.json(), {**refs, "afe_line": item}


def test_generate_bulk_assign_assumption_and_version(client: TestClient) -> None:
    headers = auth(client)
    afe, refs = submitted_afe(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "USD", "name": "US Dollar"},
        headers,
    )
    vendor = create(
        client,
        "/api/v1/master-data/vendors",
        {"code": "V-P4", "name": "Phase 4 Vendor"},
        headers,
    )
    rate = create(
        client,
        "/api/v1/master-data/rates",
        {
            "item_id": refs["service"]["id"],
            "vendor_id": vendor["id"],
            "currency_id": currency["id"],
            "unit_id": refs["day"]["id"],
            "amount": "250.00",
            "effective_from": "2026-01-01",
        },
        headers,
    )
    estimate = create(
        client,
        "/api/v1/estimates/from-afe",
        {
            "afe_id": afe["id"],
            "code": "EST-P4",
            "title": "Phase 4 cost build",
            "currency_id": currency["id"],
        },
        headers,
    )
    version = estimate["versions"][0]
    assert len(version["items"]) == 1
    assert version["items"][0]["rate_id"] is None
    assert version["items"][0]["total_cost"] is None

    assigned = client.post(
        f"/api/v1/estimates/versions/{version['id']}/bulk-assign",
        json={
            "item_ids": [version["items"][0]["id"]],
            "vendor_id": vendor["id"],
            "rate_id": rate["id"],
        },
        headers=headers,
    )
    assert assigned.status_code == 200, assigned.text

    assumption = client.put(
        f"/api/v1/estimates/versions/{version['id']}/assumptions",
        json={"contingency_percent": "10", "escalation_percent": "5"},
        headers=headers,
    )
    assert assumption.status_code == 200
    assert assumption.json()["assumptions"][0]["contingency_percent"] == "10.0000"

    duplicated = client.post(
        f"/api/v1/estimates/{estimate['id']}/versions",
        json={"notes": "Alternative vendor build"},
        headers=headers,
    )
    assert duplicated.status_code == 201
    assert duplicated.json()["version_number"] == 2
    assert duplicated.json()["items"][0]["rate_id"] == rate["id"]

    original = client.get(f"/api/v1/estimates/{estimate['id']}", headers=headers)
    assert len(original.json()["versions"]) == 2
    assert original.json()["versions"][0]["version_number"] == 1


def test_estimate_excel_export_preview_commit_round_trip(client: TestClient) -> None:
    headers = auth(client)
    afe, _refs = submitted_afe(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "EUR", "name": "Euro"},
        headers,
    )
    estimate = create(
        client,
        "/api/v1/estimates/from-afe",
        {
            "afe_id": afe["id"],
            "code": "EST-XLSX",
            "title": "Excel round trip",
            "currency_id": currency["id"],
        },
        headers,
    )
    version_id = estimate["versions"][0]["id"]
    template = client.get(f"/api/v1/estimates/versions/{version_id}/template", headers=headers)
    assert template.status_code == 200
    exported = client.get(f"/api/v1/estimates/versions/{version_id}/export", headers=headers)
    assert exported.status_code == 200
    preview = client.post(
        f"/api/v1/estimates/versions/{version_id}/import/preview",
        headers=headers,
        files={
            "file": (
                "estimate-export.xlsx",
                exported.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["status"] == "validated"
    committed = client.post(
        f"/api/v1/estimates/versions/{version_id}/import/commit",
        headers=headers,
        json={"batch_id": preview.json()["batch_id"]},
    )
    assert committed.status_code == 200
    assert committed.json()["imported_rows"] == 1


def test_draft_afe_cannot_generate_estimate(client: TestClient) -> None:
    headers = auth(client)
    _, _, afe = setup_afe(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "NGN", "name": "Naira"},
        headers,
    )
    response = client.post(
        "/api/v1/estimates/from-afe",
        json={
            "afe_id": afe["id"],
            "code": "EST-DRAFT",
            "title": "Invalid",
            "currency_id": currency["id"],
        },
        headers=headers,
    )
    assert response.status_code == 422
