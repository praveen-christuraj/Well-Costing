"""Phase 3 requirement intake API integration tests."""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def post(
    client: TestClient, path: str, payload: dict[str, Any], auth: dict[str, str]
) -> dict[str, Any]:
    response = client.post(path, json=payload, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def setup_references(client: TestClient, auth: dict[str, str]) -> dict[str, dict[str, Any]]:
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, auth)
    metre = post(client, "/api/v1/master-data/units", {"code": "M", "name": "Metre"}, auth)
    each = post(client, "/api/v1/master-data/units", {"code": "EA", "name": "Each"}, auth)
    category = post(
        client,
        "/api/v1/master-data/cost-categories",
        {"code": "SERV", "name": "Services"},
        auth,
    )
    cost_code = post(
        client,
        "/api/v1/master-data/cost-codes",
        {"code": "CC-001", "name": "Well services", "cost_category_id": category["id"]},
        auth,
    )
    service = post(
        client,
        "/api/v1/master-data/services",
        {
            "code": "SVC-001",
            "name": "Mud logging",
            "cost_category_id": category["id"],
            "cost_code_id": cost_code["id"],
            "default_unit_id": day["id"],
        },
        auth,
    )
    material = post(
        client,
        "/api/v1/master-data/materials",
        {
            "code": "MAT-001",
            "name": "Synthetic material",
            "cost_category_id": category["id"],
            "cost_code_id": cost_code["id"],
            "default_unit_id": each["id"],
        },
        auth,
    )
    return {
        "day": day,
        "metre": metre,
        "each": each,
        "category": category,
        "cost_code": cost_code,
        "service": service,
        "material": material,
    }


def setup_requirement(
    client: TestClient, auth: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    project = post(
        client,
        "/api/v1/projects",
        {"code": "PRJ-001", "name": "Synthetic drilling campaign"},
        auth,
    )
    well = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "WELL-A1", "name": "Well A1"},
        auth,
    )
    requirement = post(
        client,
        "/api/v1/requirements",
        {"well_id": well["id"], "code": "REQ-001", "title": "Drilling requirements"},
        auth,
    )
    return project, well, requirement


def test_project_well_requirement_and_bulk_item_flow(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    project, well, requirement = setup_requirement(client, auth)

    payload = {
        "rows": [
            {
                "line_number": 1,
                "catalog_item_id": refs["service"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "quantity": "2.0000",
                "unit_id": refs["day"]["id"],
                "section_name": "17.5 inch",
                "planned_duration_days": "5.0",
                "planned_depth_from": "0",
                "planned_depth_to": "1200",
                "depth_unit_id": refs["metre"]["id"],
            },
            {
                "line_number": 2,
                "catalog_item_id": refs["material"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "quantity": "100",
                "unit_id": refs["each"]["id"],
            },
        ]
    }
    validation = client.post(
        f"/api/v1/requirements/{requirement['id']}/items/bulk/validate",
        json=payload,
        headers=auth,
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    created = client.post(
        f"/api/v1/requirements/{requirement['id']}/items/bulk/create",
        json=payload,
        headers=auth,
    )
    assert created.status_code == 201, created.text
    assert len(created.json()) == 2
    assert created.json()[0]["catalog_item_code"] == "SVC-001"

    detail = client.get(f"/api/v1/requirements/{requirement['id']}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["item_count"] == 2
    assert detail.json()["project_code"] == project["code"]
    assert detail.json()["well_code"] == well["code"]

    filtered = client.get(
        f"/api/v1/requirements?project_id={project['id']}&well_id={well['id']}&status=draft",
        headers=auth,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


def test_invalid_and_inactive_catalog_references_are_rejected(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, requirement = setup_requirement(client, auth)
    client.delete(f"/api/v1/master-data/services/{refs['service']['id']}", headers=auth)

    response = client.post(
        f"/api/v1/requirements/{requirement['id']}/items",
        headers=auth,
        json={
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
        },
    )
    assert response.status_code == 422
    assert "active record" in response.json()["error"]["message"]


def test_submission_requires_items_and_prevents_silent_mutation(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, requirement = setup_requirement(client, auth)

    empty_submit = client.post(f"/api/v1/requirements/{requirement['id']}/submit", headers=auth)
    assert empty_submit.status_code == 422

    post(
        client,
        f"/api/v1/requirements/{requirement['id']}/items",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
        },
        auth,
    )
    submitted = client.post(f"/api/v1/requirements/{requirement['id']}/submit", headers=auth)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None

    mutation = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"title": "Changed after submission"},
        headers=auth,
    )
    assert mutation.status_code == 422
    assert "read-only" in mutation.json()["error"]["message"]
