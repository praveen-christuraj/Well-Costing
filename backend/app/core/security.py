"""Password hashing and JSON Web Token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

_PASSWORD_HASH = PasswordHash.recommended()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with the configured Argon2 password hasher."""

    return _PASSWORD_HASH.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password without exposing hash details."""

    return _PASSWORD_HASH.verify(plain_password, hashed_password)


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
