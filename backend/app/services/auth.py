"""Authentication application service."""

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.integrations.supabase.auth import SupabaseAuthClient
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    """Authenticate users and issue access tokens.

    Two credential sources are supported, in priority order:

    1. **Local** — the user's bcrypt/Argon2 hash in the application ``users`` table.
       This keeps existing provisioned users and the bootstrap administrator working.
    2. **Supabase Auth** — when ``SUPABASE_URL`` plus an API key are configured, a
       failed local check (or a user created in Supabase with no local password) is
       validated against Supabase Auth's password grant, and the identity is mirrored
       into the application ``users`` table.
    """

    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings
        self._supabase: SupabaseAuthClient | None = None
        if settings.supabase_auth_enabled and settings.SUPABASE_URL is not None:
            self._supabase = SupabaseAuthClient(settings.SUPABASE_URL, settings.supabase_api_key)

    def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate a user and return a bearer token."""

        normalized_email = email.strip().lower()
        user = self._users.get_by_email(normalized_email)

        if user is not None and not user.is_active:
            raise AuthenticationError("Invalid email or password")

        if user is not None and self._local_credentials_match(user, password):
            return self._issue_token(user)

        if self._supabase is not None:
            identity = self._supabase.sign_in_with_password(normalized_email, password)
            user = self._users.get_or_create_supabase_user(identity.email, identity.full_name)
            return self._issue_token(user)

        raise AuthenticationError("Invalid email or password")

    def refresh(self, user: User) -> TokenResponse:
        """Re-issue a bearer token for an already-authenticated active user.

        Tokens still expire after ``ACCESS_TOKEN_EXPIRE_MINUTES``; this lets the
        frontend slide that window forward while somebody is actively working,
        instead of interrupting them with "Invalid or expired access token" an
        hour into a data-entry session.
        """

        if not user.is_active:
            raise AuthenticationError("Invalid or expired access token")
        return self._issue_token(user)

    @staticmethod
    def _local_credentials_match(user: User, password: str) -> bool:
        """Whether a locally-hashed password verifies, with a generic false elsewhere."""

        return user.hashed_password is not None and verify_password(password, user.hashed_password)

    def _issue_token(self, user: User) -> TokenResponse:
        token = create_access_token(str(user.id))
        return TokenResponse(
            access_token=token,
            expires_in=self._settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
