"""Phase 11 cross-module invariant and authentication assurance tests."""

from fastapi.testclient import TestClient

from tests.integration.test_cost_control_framework import row, setup_estimate
from tests.integration.test_estimate_build import auth


def test_assurance_is_authenticated_and_reports_fail_closed_invariants(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/assurance/status").status_code == 401
    headers = auth(client)
    estimate, _refs = setup_estimate(client, headers)
    estimate_id = estimate["id"]
    version_id = estimate["versions"][0]["id"]

    assert (
        client.post(f"/api/v1/estimates/{estimate_id}/calculate", headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/estimates/{estimate_id}/workflow/transitions",
            json={"version_id": version_id, "action_key": "submit_for_review"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/estimates/{estimate_id}/afe/snapshots",
            json={"version_id": version_id},
            headers=headers,
        ).status_code
        == 422
    )
    staged = client.post(
        "/api/v1/cost-control/batches/validate",
        json={
            "estimate_version_id": version_id,
            "cost_state": "actual",
            "rows": [row()],
        },
        headers=headers,
    )
    assert staged.status_code == 200
    assert (
        client.post(
            f"/api/v1/cost-control/batches/{staged.json()['id']}/post", headers=headers
        ).status_code
        == 422
    )

    response = client.get("/api/v1/assurance/status", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "framework_ready"
    assert payload["migration_head"] == "20260813_0010"
    assert len(payload["checks"]) == 6
    assert all(check["status"] == "passed" for check in payload["checks"])
    assert len(payload["blockers"]) == 4
    assert all(blocker["status"] == "blocked" for blocker in payload["blockers"])
