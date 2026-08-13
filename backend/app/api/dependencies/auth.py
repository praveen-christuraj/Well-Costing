"""Authentication dependencies shared by protected routes."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().API_V1_PREFIX}/auth/login",
    auto_error=False,
)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve and validate the current active user from a bearer token."""

    if token is None:
        raise AuthenticationError("Authentication is required")
    payload = decode_access_token(token)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired access token") from exc

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid or expired access token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_system_administrator(current_user: CurrentUser) -> User:
    """Require the explicit bootstrap administrator role for configuration writes."""

    if not any(role.name == "admin" and role.is_active for role in current_user.roles):
        raise AuthorizationError("System administrator role is required")
    return current_user


SystemAdministrator = Annotated[User, Depends(get_system_administrator)]
