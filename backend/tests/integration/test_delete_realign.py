"""End-to-end coverage for the realigned edit/delete procedure.

Every user-created entry follows the same audited lifecycle:
  soft delete (DELETE /x/{id}) -> recover (POST /x/{id}/recover)
  -> permanent delete (DELETE /x/{id}/hard), which refuses with a clear
  conflict while other records still reference the entry.
"""

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


def setup_project_well_afe(
    client: TestClient, auth: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Project -> well -> AFE -> one line, referenced and ready."""

    project = post(client, "/api/v1/projects", {"code": "PRJ-DEL", "name": "Delete campaign"}, auth)
    well = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "WELL-DEL", "name": "Well Delete"},
        auth,
    )
    afe = post(
        client,
        "/api/v1/afes",
        {"well_id": well["id"], "code": "AFE-DEL", "title": "Delete flow AFE"},
        auth,
    )
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, auth)
    category = post(
        client, "/api/v1/master-data/cost-categories", {"code": "CAT-DEL", "name": "Cat"}, auth
    )
    cost_code = post(
        client,
        "/api/v1/master-data/cost-codes",
        {"code": "CC-DEL", "name": "Cost code", "cost_category_id": category["id"]},
        auth,
    )
    service = post(
        client,
        "/api/v1/master-data/services",
        {
            "code": "SVC-DEL",
            "name": "Deletion service",
            "cost_category_id": category["id"],
            "cost_code_id": cost_code["id"],
            "default_unit_id": day["id"],
        },
        auth,
    )
    line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": service["id"],
            "cost_code_id": cost_code["id"],
            "quantity": "2.0",
            "unit_id": day["id"],
        },
        auth,
    )
    return project, well, afe, line


def audit_actions(client: TestClient, auth: dict[str, str]) -> dict[str, list[str]]:
    """entity_type -> actions recorded in the global audit log."""

    page = client.get("/api/v1/audit-logs?page=1&page_size=500", headers=auth).json()
    recorded: dict[str, list[str]] = {}
    for entry in page["items"]:
        recorded.setdefault(entry["entity_type"], []).append(entry["action"])
    return recorded


def test_wells_can_be_deleted_recovered_and_permanently_deleted(
    client: TestClient,
) -> None:
    auth = headers(client)
    _project, well, afe, _ = setup_project_well_afe(client, auth)

    # Soft delete the AFE first so the well has no *active* AFE left.
    assert client.delete(f"/api/v1/afes/{afe['id']}", headers=auth).status_code == 204

    # Deleting the well is visible: it flags inactive and leaves the active list.
    assert client.delete(f"/api/v1/wells/{well['id']}", headers=auth).status_code == 204
    check = client.get(f"/api/v1/wells/{well['id']}", headers=auth).json()
    assert check["is_active"] is False
    active = client.get("/api/v1/wells?page=1&page_size=500&is_active=true", headers=auth).json()
    assert all(row["id"] != well["id"] for row in active["items"])

    # Recover works again.
    recovered = client.post(f"/api/v1/wells/{well['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["is_active"] is True

    # Recovering an active well is rejected with a clear message.
    again = client.post(f"/api/v1/wells/{well['id']}/recover", headers=auth)
    assert again.status_code == 422

    # Permanent delete refuses while any AFE (even a deleted one) references it.
    client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    client.delete(f"/api/v1/wells/{well['id']}", headers=auth)
    blocked = client.delete(f"/api/v1/wells/{well['id']}/hard", headers=auth)
    assert blocked.status_code == 409
    assert "AFE" in blocked.json()["error"]["message"]

    # Once the AFE is permanently deleted, the well can be too.
    assert client.delete(f"/api/v1/afes/{afe['id']}/hard", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/wells/{well['id']}/hard", headers=auth).status_code == 204
    assert client.get(f"/api/v1/wells/{well['id']}", headers=auth).status_code == 404

    recorded = audit_actions(client, auth)
    assert "soft_delete" in recorded["well"]
    assert "recover" in recorded["well"]
    assert "hard_delete" in recorded["well"]


def test_projects_can_be_deleted_recovered_and_permanently_deleted(
    client: TestClient,
) -> None:
    auth = headers(client)
    project, well, afe, _ = setup_project_well_afe(client, auth)

    assert client.delete(f"/api/v1/projects/{project['id']}", headers=auth).status_code == 204
    recovered = client.post(f"/api/v1/projects/{project['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["is_active"] is True

    # Permanent delete refuses while wells still belong to the project.
    client.delete(f"/api/v1/projects/{project['id']}", headers=auth)
    blocked = client.delete(f"/api/v1/projects/{project['id']}/hard", headers=auth)
    assert blocked.status_code == 409
    assert "well" in blocked.json()["error"]["message"].lower()

    # Tear the chain down: AFE -> well -> project.
    client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    assert client.delete(f"/api/v1/afes/{afe['id']}/hard", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/wells/{well['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/wells/{well['id']}/hard", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/projects/{project['id']}/hard", headers=auth).status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}", headers=auth).status_code == 404

    recorded = audit_actions(client, auth)
    assert "soft_delete" in recorded["project"]
    assert "recover" in recorded["project"]
    assert "hard_delete" in recorded["project"]


def test_hard_deleting_afe_with_estimate_conflicts_instead_of_crashing(
    client: TestClient,
) -> None:
    """The reported bug: 'Delete forever' on a deleted AFE raised a 500."""

    auth = headers(client)
    _project, _well, afe, _ = setup_project_well_afe(client, auth)
    assert client.post(f"/api/v1/afes/{afe['id']}/submit", headers=auth).status_code == 200
    currency = post(
        client, "/api/v1/master-data/currencies", {"code": "USD", "name": "Dollar"}, auth
    )
    estimate = post(
        client,
        "/api/v1/estimates/from-afe",
        {
            "afe_id": afe["id"],
            "code": "EST-DEL",
            "title": "Blocking estimate",
            "currency_id": currency["id"],
        },
        auth,
    )

    client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    blocked = client.delete(f"/api/v1/afes/{afe['id']}/hard", headers=auth)
    assert blocked.status_code == 409
    assert "estimate" in blocked.json()["error"]["message"].lower()

    # Deleting the estimate (soft then permanent) unblocks the AFE deletion.
    assert client.delete(f"/api/v1/estimates/{estimate['id']}", headers=auth).status_code == 204
    assert (
        client.delete(f"/api/v1/estimates/{estimate['id']}/hard", headers=auth).status_code == 204
    )
    assert client.delete(f"/api/v1/afes/{afe['id']}/hard", headers=auth).status_code == 204
    assert client.get(f"/api/v1/afes/{afe['id']}", headers=auth).status_code == 404


def test_estimates_follow_the_same_delete_procedure(client: TestClient) -> None:
    auth = headers(client)
    _project, _well, afe, _ = setup_project_well_afe(client, auth)
    assert client.post(f"/api/v1/afes/{afe['id']}/submit", headers=auth).status_code == 200
    currency = post(client, "/api/v1/master-data/currencies", {"code": "EUR", "name": "Euro"}, auth)
    estimate = post(
        client,
        "/api/v1/estimates/from-afe",
        {
            "afe_id": afe["id"],
            "code": "EST-LIFE",
            "title": "Lifecycle estimate",
            "currency_id": currency["id"],
        },
        auth,
    )

    # Permanent delete is refused before the soft delete happened.
    too_early = client.delete(f"/api/v1/estimates/{estimate['id']}/hard", headers=auth)
    assert too_early.status_code == 422

    # Soft delete hides it from the builder's active list.
    assert client.delete(f"/api/v1/estimates/{estimate['id']}", headers=auth).status_code == 204
    active = client.get(
        "/api/v1/estimates?page=1&page_size=500&is_active=true", headers=auth
    ).json()
    assert all(row["id"] != estimate["id"] for row in active["items"])
    deleted = client.get(
        "/api/v1/estimates?page=1&page_size=500&is_active=false", headers=auth
    ).json()
    assert any(row["id"] == estimate["id"] for row in deleted["items"])

    # Deleting twice is rejected clearly instead of duplicating state.
    twice = client.delete(f"/api/v1/estimates/{estimate['id']}", headers=auth)
    assert twice.status_code == 422

    # Recover restores it.
    recovered = client.post(f"/api/v1/estimates/{estimate['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["is_active"] is True

    # And the permanent delete works after a fresh soft delete.
    client.delete(f"/api/v1/estimates/{estimate['id']}", headers=auth)
    assert (
        client.delete(f"/api/v1/estimates/{estimate['id']}/hard", headers=auth).status_code == 204
    )
    assert client.get(f"/api/v1/estimates/{estimate['id']}", headers=auth).status_code == 404

    recorded = audit_actions(client, auth)
    assert "create" in recorded["estimate"]
    assert "soft_delete" in recorded["estimate"]
    assert "recover" in recorded["estimate"]
    assert "hard_delete" in recorded["estimate"]


def test_removed_afe_line_disappears_and_can_be_recovered(client: TestClient) -> None:
    auth = headers(client)
    _, _, afe, line = setup_project_well_afe(client, auth)

    assert client.delete(f"/api/v1/afe-lines/{line['id']}", headers=auth).status_code == 204

    # The removed line no longer clutters the lines workspace…
    lines = client.get(f"/api/v1/afes/{afe['id']}/lines", headers=auth).json()
    assert lines == []
    detail = client.get(f"/api/v1/afes/{afe['id']}", headers=auth).json()
    assert detail["item_count"] == 0
    assert detail["items"] == []

    # …but is offered for recovery.
    removed = client.get(f"/api/v1/afes/{afe['id']}/lines/removed", headers=auth).json()
    assert [row["id"] for row in removed] == [line["id"]]

    recovered = client.post(f"/api/v1/afe-lines/{line['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["is_active"] is True
    lines_after = client.get(f"/api/v1/afes/{afe['id']}/lines", headers=auth).json()
    assert [row["id"] for row in lines_after] == [line["id"]]

    recorded = audit_actions(client, auth)
    assert "soft_delete" in recorded["afe_line"]
    assert "recover" in recorded["afe_line"]


def test_drilling_phase_delete_and_recover(client: TestClient) -> None:
    auth = headers(client)
    phase = post(
        client,
        "/api/v1/drilling-phases",
        {"code": "STIM", "name": "Stimulation", "sequence": 99},
        auth,
    )
    assert client.delete(f"/api/v1/drilling-phases/{phase['id']}", headers=auth).status_code == 204
    recovered = client.post(f"/api/v1/drilling-phases/{phase['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["is_active"] is True


def test_daily_cost_entry_delete_is_soft_and_recoverable(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_project_well_afe(client, auth)
    well_id = refs[1]["id"]

    entry = post(
        client,
        f"/api/v1/wells/{well_id}/daily-cost",
        {
            "well_id": well_id,
            "entry_date": "2026-08-01",
            "phase": "Drilling",
            "services": [],
            "consumables": [],
        },
        auth,
    )

    assert (
        client.delete(f"/api/v1/wells/{well_id}/daily-cost/{entry['id']}", headers=auth).status_code
        == 204
    )
    entries = client.get(f"/api/v1/wells/{well_id}/daily-cost", headers=auth).json()
    assert all(row["id"] != entry["id"] for row in entries)

    recovered = client.post(
        f"/api/v1/wells/{well_id}/daily-cost/{entry['id']}/recover", headers=auth
    )
    assert recovered.status_code == 200
    entries_after = client.get(f"/api/v1/wells/{well_id}/daily-cost", headers=auth).json()
    assert any(row["id"] == entry["id"] for row in entries_after)

    recorded = audit_actions(client, auth)
    assert "soft_delete" in recorded["daily_cost_entry"]
    assert "recover" in recorded["daily_cost_entry"]


def test_soft_deleted_well_is_rejected_for_new_afes_but_editable(
    client: TestClient,
) -> None:
    auth = headers(client)
    _project, well, afe, _ = setup_project_well_afe(client, auth)
    client.delete(f"/api/v1/afes/{afe['id']}", headers=auth)
    client.delete(f"/api/v1/wells/{well['id']}", headers=auth)

    rejected = client.post(
        "/api/v1/afes",
        json={"well_id": well["id"], "code": "AFE-REJ", "title": "Must fail"},
        headers=auth,
    )
    assert rejected.status_code == 422

    # An existing entry of a deleted well can still be edited and recovered.
    edited = client.patch(
        f"/api/v1/wells/{well['id']}", json={"name": "Renamed well"}, headers=auth
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Renamed well"
    recovered = client.post(f"/api/v1/wells/{well['id']}/recover", headers=auth)
    assert recovered.status_code == 200
    assert recovered.json()["name"] == "Renamed well"
    assert recovered.json()["is_active"] is True
