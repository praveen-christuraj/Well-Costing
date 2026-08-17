"""Supabase Auth client unit tests."""

import json
from collections.abc import Callable

import httpx
import pytest
from app.core.exceptions import AuthenticationError, AuthServiceUnavailableError
from app.integrations.supabase.auth import SupabaseAuthClient, SupabaseIdentity

SUPABASE_URL = "https://example.supabase.co"
ANON_KEY = "anon-test-key"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> SupabaseAuthClient:
    transport = httpx.MockTransport(handler)
    return SupabaseAuthClient(
        SUPABASE_URL,
        ANON_KEY,
        client=httpx.Client(transport=transport),
    )


def test_sign_in_with_password_returns_canonical_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        assert request.headers["apikey"] == ANON_KEY
        assert request.headers["authorization"] == f"Bearer {ANON_KEY}"
        assert json.loads(request.content) == {
            "email": "engineer@example.com",
            "password": "pw",
        }
        return httpx.Response(
            200,
            json={
                "access_token": "sb-token",
                "user": {
                    "id": "user-uuid-1",
                    "email": "ENGINEER@example.com",
                    "user_metadata": {"full_name": "  Test Engineer  "},
                },
            },
        )

    identity = _client(handler).sign_in_with_password(" engineer@example.com ", "pw")

    assert identity == SupabaseIdentity(
        id="user-uuid-1",
        email="engineer@example.com",
        full_name="Test Engineer",
    )


def test_full_name_falls_back_to_email_local_part() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "sb-token",
                "user": {
                    "id": "user-uuid-2",
                    "email": "john.doe@example.com",
                    "user_metadata": {},
                },
            },
        )

    identity = _client(handler).sign_in_with_password("john.doe@example.com", "pw")

    assert identity.full_name == "John Doe"


def test_invalid_credentials_raise_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Invalid login credentials"},
        )

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        _client(handler).sign_in_with_password("engineer@example.com", "wrong")


def test_server_error_raises_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    with pytest.raises(AuthServiceUnavailableError):
        _client(handler).sign_in_with_password("engineer@example.com", "pw")


def test_network_failure_raises_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("cannot reach Supabase")

    with pytest.raises(AuthServiceUnavailableError):
        _client(handler).sign_in_with_password("engineer@example.com", "pw")


def test_unexpected_success_payload_raises_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "sb-token"})

    with pytest.raises(AuthServiceUnavailableError):
        _client(handler).sign_in_with_password("engineer@example.com", "pw")
