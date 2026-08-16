"""Password hashing and JSON Web Token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import HasherNotAvailable, UnknownHashError
from pwdlib.hashers import HasherProtocol
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

# Password hashers, in preference order (hashers[0] produces new hashes).
# bcrypt is the guaranteed baseline: its wheels cover every platform this
# backend runs on, including the minimal manylinux_2_17 (glibc 2.17) tag set of
# long-lived proot-distro Debian containers on Termux, where
# argon2-cffi-bindings (manylinux_2_26+) publishes no usable aarch64 wheel.
# When the optional ``argon2`` extra is installed (desktop/cloud), Argon2id
# stays the primary hasher and the bcrypt hasher additionally verifies hashes
# created by bcrypt-only deployments, so user passwords remain portable between
# environments.
_PASSWORD_HASHERS: list[HasherProtocol] = [BcryptHasher()]
try:
    from pwdlib.hashers.argon2 import Argon2Hasher
except HasherNotAvailable:  # argon2-cffi is not installed in this environment
    pass
else:
    _PASSWORD_HASHERS.insert(0, Argon2Hasher())

_PASSWORD_HASH = PasswordHash(_PASSWORD_HASHERS)
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with the strongest available password hasher."""

    return _PASSWORD_HASH.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password without exposing hash details.

    A stored hash whose scheme is unavailable in this environment (e.g. an
    Argon2 hash on a bcrypt-only install) is treated as a normal credential
    mismatch instead of raising, so login answers 401 rather than 500.
    """

    try:
        return _PASSWORD_HASH.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed access token for a stable user subject."""

    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        payload, settings.SECRET_KEY, algorithm=_ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed access token.

    Raises a normalized :class:`AuthenticationError` for all invalid-token cases.
    """

    try:
        payload: dict[str, Any] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            get_settings().SECRET_KEY,
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc

    if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise AuthenticationError("Invalid or expired access token")
    return payload
