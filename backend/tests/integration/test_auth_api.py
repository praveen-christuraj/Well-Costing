"""Authentication API integration tests."""

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def test_login_and_me_round_trip(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ENGINEER@example.com", "password": TEST_PASSWORD},
    )

    assert login.status_code == 200
    token_payload = login.json()
    assert token_payload["token_type"] == "bearer"
    assert token_payload["expires_in"] == 3600

    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "engineer@example.com"
    assert profile.json()["full_name"] == "Test Engineer"
    assert "hashed_password" not in profile.json()


def test_login_failure_uses_normalized_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Invalid email or password",
            "details": None,
        }
    }


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_request_validation_uses_error_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
