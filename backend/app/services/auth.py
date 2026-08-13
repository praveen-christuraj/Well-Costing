"""Authentication application service."""

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    """Authenticate users and issue access tokens."""

    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def authenticate(self, email: str, password: str) -> User:
        """Validate credentials using a deliberately generic failure message."""

        user = self._users.get_by_email(email)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid email or password")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        return user

    def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate a user and return a bearer token."""

        user = self.authenticate(email, password)
        token = create_access_token(str(user.id))
        return TokenResponse(
            access_token=token,
            expires_in=self._settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
