"""Phase 6 pending workflow, transition audit, and review-comment tests."""

from fastapi.testclient import TestClient

from tests.integration.test_estimate_build import auth, create, submitted_afe


def estimate_for_review(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    afe, _refs = submitted_afe(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "CAD", "name": "Canadian Dollar"},
        headers,
    )
    return create(
        client,
        "/api/v1/estimates/from-afe",
        {
            "afe_id": afe["id"],
            "code": "EST-P6-REVIEW",
            "title": "Pending review workflow",
            "currency_id": currency["id"],
        },
        headers,
    )


def test_unpublished_workflow_blocks_and_audits_transition_without_state_change(
    client: TestClient,
) -> None:
    headers = auth(client)
    estimate = estimate_for_review(client, headers)
    estimate_id = estimate["id"]

    profiles = client.get("/api/v1/workflow/profiles", headers=headers)
    assert profiles.status_code == 200
    assert profiles.json() == []

    initial = client.get(f"/api/v1/estimates/{estimate_id}/workflow", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["workflow_status"] == "profile_pending"
    assert initial.json()["profile"] is None
    assert initial.json()["current_state_key"] is None
    assert initial.json()["available_actions"] == []
    assert len(initial.json()["pending_requirements"]) == 6

    transition = client.post(
        f"/api/v1/estimates/{estimate_id}/workflow/transitions",
        json={"action_key": "submit_for_review"},
        headers=headers,
    )
    assert transition.status_code == 422
    error = transition.json()["error"]
    assert error["code"] == "workflow_profile_pending"
    assert error["details"]["transition_attempt_id"]
    assert error["details"]["workflow_policy_version"] == "pending-estimate-review"

    after = client.get(f"/api/v1/estimates/{estimate_id}/workflow", headers=headers)
    assert after.status_code == 200
    assert after.json()["workflow_status"] == "profile_pending"
    attempt = after.json()["transition_attempts"][0]
    assert attempt["status"] == "blocked"
    assert attempt["requested_action"] == "submit_for_review"
    assert attempt["created_by"] is not None
    assert attempt["context_snapshot"]["version_number"] == 1

    unchanged = client.get(f"/api/v1/estimates/{estimate_id}", headers=headers)
    version = unchanged.json()["versions"][0]
    assert version["status"] == "pending_calculation"
    assert version["grand_total"] is None


def test_authenticated_review_comment_is_immutable_audit_input(client: TestClient) -> None:
    headers = auth(client)
    estimate = estimate_for_review(client, headers)
    estimate_id = estimate["id"]

    created = client.post(
        f"/api/v1/estimates/{estimate_id}/review-comments",
        json={"body": "Confirm the selected vendor before any approval policy is activated."},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["created_by"] is not None

    comments = client.get(f"/api/v1/estimates/{estimate_id}/review-comments", headers=headers)
    assert comments.status_code == 200
    assert len(comments.json()) == 1
    assert comments.json()[0]["body"].startswith("Confirm the selected vendor")
