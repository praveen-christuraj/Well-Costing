"""AFE preparation API integration tests."""

from decimal import Decimal
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
    surface_section = post(
        client,
        "/api/v1/master-data/hole-sections",
        {"code": "17-1/2", "name": "17-1/2 inch hole"},
        auth,
    )
    intermediate_section = post(
        client,
        "/api/v1/master-data/hole-sections",
        {"code": "12-1/4", "name": "12-1/4 inch hole"},
        auth,
    )
    mud_chemical = post(
        client,
        "/api/v1/master-data/mud-chemicals",
        {
            "code": "MUD-001",
            "name": "Barite",
            "cost_category_id": category["id"],
            "cost_code_id": cost_code["id"],
            "default_unit_id": each["id"],
            "rate_basis": "daily_consumption",
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
        "mud_chemical": mud_chemical,
        "surface_section": surface_section,
        "intermediate_section": intermediate_section,
    }


def setup_afe(
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
    afe = post(
        client,
        "/api/v1/afes",
        {"well_id": well["id"], "code": "REQ-001", "title": "Drilling afes"},
        auth,
    )
    return project, well, afe


def test_project_well_afe_and_bulk_line_flow(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    project, well, afe = setup_afe(client, auth)

    payload = {
        "rows": [
            {
                "line_number": 1,
                "catalog_item_id": refs["service"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "quantity": "2.0000",
                "unit_id": refs["day"]["id"],
                "hole_section_id": refs["surface_section"]["id"],
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
        f"/api/v1/afes/{afe['id']}/lines/bulk/validate",
        json=payload,
        headers=auth,
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    created = client.post(
        f"/api/v1/afes/{afe['id']}/lines/bulk/create",
        json=payload,
        headers=auth,
    )
    assert created.status_code == 201, created.text
    assert len(created.json()) == 2
    assert created.json()[0]["catalog_item_code"] == "SVC-001"

    detail = client.get(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["item_count"] == 2
    assert detail.json()["project_code"] == project["code"]
    assert detail.json()["well_code"] == well["code"]

    filtered = client.get(
        f"/api/v1/afes?project_id={project['id']}&well_id={well['id']}&status=draft",
        headers=auth,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


def test_invalid_and_inactive_catalog_references_are_rejected(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)
    client.delete(f"/api/v1/master-data/services/{refs['service']['id']}", headers=auth)

    response = client.post(
        f"/api/v1/afes/{afe['id']}/lines",
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
    _, _, afe = setup_afe(client, auth)

    empty_submit = client.post(f"/api/v1/afes/{afe['id']}/submit", headers=auth)
    assert empty_submit.status_code == 422

    post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
        },
        auth,
    )
    submitted = client.post(f"/api/v1/afes/{afe['id']}/submit", headers=auth)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None

    mutation = client.patch(
        f"/api/v1/afes/{afe['id']}",
        json={"title": "Changed after submission"},
        headers=auth,
    )
    assert mutation.status_code == 422
    assert "read-only" in mutation.json()["error"]["message"]


def test_draft_afe_can_be_deleted_outright(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
        },
        auth,
    )

    deleted = client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert deleted.status_code == 204

    gone = client.get(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert gone.status_code == 404

    remaining = client.get("/api/v1/afes?page=1&page_size=500", headers=auth)
    assert remaining.json()["total"] == 0


def test_submitted_afe_cannot_be_deleted(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
        },
        auth,
    )
    assert client.post(f"/api/v1/afes/{afe['id']}/submit", headers=auth).status_code == 200

    deleted = client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert deleted.status_code == 422
    assert "read-only" in deleted.json()["error"]["message"]


def test_section_must_be_a_configured_hole_section(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 3,
            "unit_id": refs["day"]["id"],
            "hole_section_id": refs["surface_section"]["id"],
        },
        auth,
    )
    assert line["hole_section_code"] == "17-1/2"
    assert line["hole_section_name"] == "17-1/2 inch hole"

    unknown = client.post(
        f"/api/v1/afes/{afe['id']}/lines",
        headers=auth,
        json={
            "line_number": 2,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 3,
            "unit_id": refs["day"]["id"],
            "hole_section_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert unknown.status_code == 422
    assert "hole_section_id" in unknown.json()["error"]["message"]


def test_line_rate_basis_defaults_from_the_catalogue_and_can_be_overridden(
    client: TestClient,
) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    default_line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 4,
            "unit_id": refs["day"]["id"],
        },
        auth,
    )
    assert default_line["rate_basis"] == "daily"

    per_section = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 2,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
            "rate_basis": "per_section",
            "hole_section_id": refs["intermediate_section"]["id"],
        },
        auth,
    )
    assert per_section["rate_basis"] == "per_section"

    missing_section = client.post(
        f"/api/v1/afes/{afe['id']}/lines",
        headers=auth,
        json={
            "line_number": 3,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
            "rate_basis": "per_section",
        },
    )
    assert missing_section.status_code == 422
    assert "charged per section" in missing_section.json()["error"]["message"]

    wrong_basis = client.post(
        f"/api/v1/afes/{afe['id']}/lines",
        headers=auth,
        json={
            "line_number": 4,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
            "rate_basis": "daily_consumption",
        },
    )
    assert wrong_basis.status_code == 422
    assert "not valid for service" in wrong_basis.json()["error"]["message"]


def test_chemical_quantity_is_computed_from_daily_usage_and_planned_days(
    client: TestClient,
) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    computed = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["mud_chemical"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "unit_id": refs["each"]["id"],
            "daily_consumption": 20,
            "planned_duration_days": 6,
        },
        auth,
    )
    assert computed["rate_basis"] == "daily_consumption"
    assert Decimal(computed["quantity"]) == Decimal(120)
    assert Decimal(computed["computed_quantity"]) == Decimal(120)
    assert computed["quantity_source"] == "computed"

    unexplained = client.post(
        f"/api/v1/afes/{afe['id']}/lines",
        headers=auth,
        json={
            "line_number": 2,
            "catalog_item_id": refs["mud_chemical"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 150,
            "unit_id": refs["each"]["id"],
            "daily_consumption": 20,
            "planned_duration_days": 6,
        },
    )
    assert unexplained.status_code == 422
    assert "quantity_override_reason" in unexplained.json()["error"]["message"]

    overridden = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 3,
            "catalog_item_id": refs["mud_chemical"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 150,
            "unit_id": refs["each"]["id"],
            "daily_consumption": 20,
            "planned_duration_days": 6,
            "quantity_override_reason": "Contingency stock held at the rig site",
        },
        auth,
    )
    assert Decimal(overridden["quantity"]) == Decimal(150)
    assert Decimal(overridden["computed_quantity"]) == Decimal(120)
    assert overridden["quantity_source"] == "overridden"

    recomputed = client.patch(
        f"/api/v1/afe-lines/{computed['id']}",
        headers=auth,
        json={"planned_duration_days": 10},
    )
    assert recomputed.status_code == 200, recomputed.text
    assert Decimal(recomputed.json()["quantity"]) == Decimal(200)
    assert recomputed.json()["quantity_source"] == "computed"


def test_get_afe_survives_orphaned_catalogue_reference(client: TestClient) -> None:
    """GET /afes/{id} must not 500 when a referenced catalogue item is missing.

    Regression: ``AfeLineService.read`` and ``AfeService._read`` accessed
    relationship attributes without a None guard, so an AFE line whose catalogue
    item / cost code / unit had been hard-deleted crashed the whole AFE detail
    endpoint with an unhandled AttributeError (HTTP 500, "An unexpected error
    occurred"). The serializers now degrade to null placeholders instead.
    """
    auth = headers(client)
    refs = setup_references(client, auth)
    _, _, afe = setup_afe(client, auth)

    line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": refs["service"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": 1,
            "unit_id": refs["day"]["id"],
            "rate_basis": "daily",
        },
        auth,
    )
    assert line["catalog_item_code"] == "SVC-001"

    # Permanently delete every referenced record (the FK is not enforced in the
    # in-memory SQLite test DB, mirroring legacy/orphaned data).
    for entity, record_id in (
        ("services", refs["service"]["id"]),
        ("cost-codes", refs["cost_code"]["id"]),
        ("units", refs["day"]["id"]),
    ):
        deleted = client.delete(
            f"/api/v1/master-data/{entity}/{record_id}?hard=true",
            headers=auth,
        )
        assert deleted.status_code == 204, deleted.text

    detail = client.get(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert detail.status_code == 200, detail.text
    items = detail.json()["items"]
    assert len(items) == 1
    assert items[0]["catalog_item_code"] is None
    assert items[0]["catalog_item_name"] is None
    assert items[0]["item_type"] is None
    assert items[0]["cost_code"] is None
    assert items[0]["unit_code"] is None
    assert detail.json()["item_count"] == 1
