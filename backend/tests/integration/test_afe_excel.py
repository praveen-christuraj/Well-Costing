"""The retired AFE-line spreadsheet module must not leak into active routing."""

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def test_retired_afe_line_excel_routes_are_not_registered(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    afe_id = "00000000-0000-0000-0000-000000000001"

    for method, path in (
        ("get", f"/api/v1/afes/{afe_id}/export"),
        ("get", f"/api/v1/afes/{afe_id}/import/template"),
        ("post", f"/api/v1/afes/{afe_id}/import/commit"),
    ):
        response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 404, response.text
