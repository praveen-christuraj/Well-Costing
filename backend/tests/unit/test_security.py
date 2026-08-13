"""Security helper unit tests."""

from datetime import timedelta

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password = "A-long-development-password!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("incorrect-password", hashed)


def test_access_token_round_trip() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))

    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        decode_access_token(token)


def test_malformed_access_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        decode_access_token("not-a-jwt")
