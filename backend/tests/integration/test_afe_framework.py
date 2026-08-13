"""Phase 7 blocked baseline AFE snapshot and audit tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.integration.test_estimate_build import auth, create, submitted_requirement


def test_baseline_afe_creation_is_blocked_and_audited_without_policy(
    client: TestClient,
) -> None:
    headers = auth(client)
    requirement, _refs = submitted_requirement(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "AUD", "name": "Australian Dollar"},
        headers,
    )
    estimate = create(
        client,
        "/api/v1/estimates/from-requirement",
        {
            "requirement_id": requirement["id"],
            "code": "EST-P7-AFE",
            "title": "Pending baseline AFE",
            "currency_id": currency["id"],
        },
        headers,
    )
    estimate_id = estimate["id"]

    initial = client.get(f"/api/v1/estimates/{estimate_id}/afe", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["afe_status"] == "policy_pending"
    assert initial.json()["baseline_snapshot"] is None
    assert len(initial.json()["pending_requirements"]) == 6

    response = client.post(
        f"/api/v1/estimates/{estimate_id}/afe/snapshots",
        json={"requested_reference": "DO-NOT-ISSUE-001"},
        headers=headers,
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "afe_policy_pending"
    assert error["details"]["afe_policy_version"] == "pending-baseline-afe"
    assert error["details"]["snapshot_attempt_id"]

    after = client.get(f"/api/v1/estimates/{estimate_id}/afe", headers=headers)
    assert after.status_code == 200
    attempt = after.json()["creation_attempts"][0]
    assert attempt["status"] == "blocked"
    assert attempt["requested_reference"] == "DO-NOT-ISSUE-001"
    assert attempt["created_by"] is not None
    assert attempt["eligibility_snapshot"]["workflow_instance_id"] is None
    assert attempt["eligibility_snapshot"]["calculation_run_id"] is None
    assert attempt["eligibility_snapshot"]["totals_complete"] is False
    assert after.json()["baseline_snapshot"] is None

    unchanged = client.get(f"/api/v1/estimates/{estimate_id}", headers=headers)
    version = unchanged.json()["versions"][0]
    assert version["status"] == "pending_calculation"
    assert version["grand_total"] is None
    assert version["items"][0]["total_cost"] is None

    missing = client.get(f"/api/v1/afes/{uuid4()}", headers=headers)
    assert missing.status_code == 404
