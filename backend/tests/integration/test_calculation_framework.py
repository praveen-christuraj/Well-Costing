"""Phase 5 calculation framework and blocked-rule audit tests."""

from fastapi.testclient import TestClient

from tests.integration.test_estimate_build import auth, create, submitted_requirement


def test_calculation_is_blocked_and_audited_without_confirmed_rules(
    client: TestClient,
) -> None:
    headers = auth(client)
    requirement, _refs = submitted_requirement(client, headers)
    currency = create(
        client,
        "/api/v1/master-data/currencies",
        {"code": "GBP", "name": "Pound Sterling"},
        headers,
    )
    estimate = create(
        client,
        "/api/v1/estimates/from-requirement",
        {
            "requirement_id": requirement["id"],
            "code": "EST-P5-BLOCKED",
            "title": "Blocked calculation framework",
            "currency_id": currency["id"],
        },
        headers,
    )
    response = client.post(f"/api/v1/estimates/{estimate['id']}/calculate", headers=headers)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "business_rule_pending"
    assert len(error["details"]["pending_rules"]) == 7
    assert error["details"]["calculation_run_id"]

    results = client.get(f"/api/v1/estimates/{estimate['id']}/results", headers=headers)
    assert results.status_code == 200
    assert results.json()["calculation_status"] == "blocked"
    assert results.json()["grand_total"] is None
    assert results.json()["calculation_runs"][0]["status"] == "blocked"
    assert (
        results.json()["calculation_runs"][0]["input_snapshot"]["lines"][0]["item_code"]
        == "SVC-001"
    )

    unchanged = client.get(f"/api/v1/estimates/{estimate['id']}", headers=headers)
    assert unchanged.status_code == 200
    version = unchanged.json()["versions"][0]
    assert [
        version["base_total"],
        version["contingency_total"],
        version["escalation_total"],
        version["grand_total"],
    ] == [None, None, None, None]
    assert [
        version["items"][0]["base_cost"],
        version["items"][0]["contingency_cost"],
        version["items"][0]["escalation_cost"],
        version["items"][0]["total_cost"],
    ] == [None, None, None, None]
