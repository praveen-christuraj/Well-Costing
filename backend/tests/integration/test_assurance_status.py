"""Authentication and active data-chain assurance tests."""

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def test_assurance_checks_active_afe_daily_cost_invariants(client: TestClient) -> None:
    assert client.get("/api/v1/assurance/status").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/assurance/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "framework_ready"
    assert payload["migration_head"] == "20260825_0027"
    assert payload["reporting_contract_version"] == "2.0"
    assert {check["key"] for check in payload["checks"]} == {
        "afe_classification",
        "estimate_line_scope",
        "daily_cost_source",
        "daily_cost_totals",
        "daily_activity_scope",
    }
    assert all(check["status"] == "passed" for check in payload["checks"])
    assert payload["blockers"] == []
