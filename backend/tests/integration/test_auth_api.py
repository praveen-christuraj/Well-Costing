"""Authentication API integration tests."""

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthServiceUnavailableError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.integrations.supabase.auth import SupabaseIdentity
from app.main import create_app
from app.models import User
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD

SUPABASE_PASSWORD = "Supabase-Password-2026!"


def _supabase_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        CORS_ORIGINS=["http://testserver"],
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon-test-key",
    )


@contextmanager
def _supabase_client(db_session: Session) -> Generator[TestClient, None, None]:
    application = create_app(_supabase_settings())

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_settings() -> Settings:
        return _supabase_settings()

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_settings] = override_get_settings
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


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


def test_refresh_reissues_token_for_an_active_session(client: TestClient) -> None:
    """The sliding refresh: a still-valid token buys a fresh one, quietly."""

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    old_token = login.json()["access_token"]

    refreshed = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {old_token}"})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    # Same subject, freshly signed token with a new expiry.
    assert decode_access_token(body["access_token"])["sub"] == decode_access_token(old_token)["sub"]
    assert decode_access_token(body["access_token"])["exp"] >= decode_access_token(old_token)["exp"]

    profile = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "engineer@example.com"


def test_refresh_rejects_missing_and_garbage_tokens(client: TestClient) -> None:
    assert client.post("/api/v1/auth/refresh").status_code == 401

    garbage = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": "Bearer not-a-token"}
    )
    assert garbage.status_code == 401
    assert garbage.json()["error"]["code"] == "authentication_failed"


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


def test_supabase_auth_user_can_login_and_is_mirrored(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.auth as auth_service_module

    class FakeSupabaseAuthClient:
        def __init__(self, url: str, api_key: str, **kwargs: object) -> None:
            pass

        def sign_in_with_password(self, email: str, password: str) -> SupabaseIdentity:
            if password != SUPABASE_PASSWORD:
                raise AuthenticationError("Invalid email or password")
            return SupabaseIdentity(
                id="supabase-user-id",
                email=email,
                full_name="Supabase Person",
            )

    monkeypatch.setattr(auth_service_module, "SupabaseAuthClient", FakeSupabaseAuthClient)

    with _supabase_client(db_session) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "SUPABASE.USER@example.com", "password": SUPABASE_PASSWORD},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        profile = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile.status_code == 200
        assert profile.json()["email"] == "supabase.user@example.com"
        assert profile.json()["full_name"] == "Supabase Person"

    user = db_session.scalar(select(User).where(User.email == "supabase.user@example.com"))
    assert user is not None
    assert user.auth_provider == "supabase"
    assert user.hashed_password is None


def test_local_password_still_works_when_supabase_configured(
    db_session: Session, seeded_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.auth as auth_service_module

    class FakeSupabaseAuthClient:
        def __init__(self, url: str, api_key: str, **kwargs: object) -> None:
            pass

        def sign_in_with_password(self, email: str, password: str) -> SupabaseIdentity:
            raise AssertionError("Supabase must not be called for a matching local password")

    monkeypatch.setattr(auth_service_module, "SupabaseAuthClient", FakeSupabaseAuthClient)
    del seeded_user

    with _supabase_client(db_session) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "engineer@example.com", "password": TEST_PASSWORD},
        )
        assert login.status_code == 200
        assert login.json()["token_type"] == "bearer"


def test_supabase_rejection_returns_normalized_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.auth as auth_service_module

    class FakeSupabaseAuthClient:
        def __init__(self, url: str, api_key: str, **kwargs: object) -> None:
            pass

        def sign_in_with_password(self, email: str, password: str) -> SupabaseIdentity:
            raise AuthenticationError("Invalid email or password")

    monkeypatch.setattr(auth_service_module, "SupabaseAuthClient", FakeSupabaseAuthClient)

    with _supabase_client(db_session) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "Wrong-Password-2026!"},
        )
        assert login.status_code == 401
        assert login.json()["error"]["code"] == "authentication_failed"


def test_supabase_unavailable_returns_service_unavailable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.auth as auth_service_module

    class FakeSupabaseAuthClient:
        def __init__(self, url: str, api_key: str, **kwargs: object) -> None:
            pass

        def sign_in_with_password(self, email: str, password: str) -> SupabaseIdentity:
            raise AuthServiceUnavailableError(
                "Unable to reach the authentication service. Please try again."
            )

    monkeypatch.setattr(auth_service_module, "SupabaseAuthClient", FakeSupabaseAuthClient)

    with _supabase_client(db_session) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "Whatever-Password-2026!"},
        )
        assert login.status_code == 503
        assert login.json()["error"]["code"] == "auth_service_unavailable"
