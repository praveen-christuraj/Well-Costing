"""Security helper unit tests."""

from datetime import timedelta

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    _PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from pwdlib.hashers.bcrypt import BcryptHasher


def test_password_hash_round_trip() -> None:
    password = "A-long-development-password!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("incorrect-password", hashed)


def test_bcrypt_hasher_is_always_configured() -> None:
    """bcrypt must stay in the hasher chain regardless of the argon2 extra.

    This is the invariant that keeps password hashes portable to the Termux
    deployment, where argon2-cffi-bindings has no usable aarch64 wheel and only
    bcrypt is available.
    """

    assert any(isinstance(hasher, BcryptHasher) for hasher in _PASSWORD_HASH.hashers)


def test_verify_password_handles_unavailable_hash_scheme() -> None:
    """A hash for a scheme not installed here counts as a credential mismatch."""

    # Argon2-encoded dummy; correct or not, it must never raise to the caller.
    argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$YWJjZA$AAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert verify_password("whatever-password", argon2_hash) is False


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
