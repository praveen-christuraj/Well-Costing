"""User persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Typed SQLAlchemy access for users."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        """Return one user by primary key."""

        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return one user by normalized email."""

        statement = select(User).where(User.email == email.strip().lower())
        return self._session.scalar(statement)

    def get_or_create_supabase_user(self, email: str, full_name: str) -> User:
        """Mirror a Supabase Auth identity as a local user, creating it on first login.

        A Supabase-authenticated user has no local password hash, so the record is
        marked ``auth_provider="supabase"`` and keeps its email, display name, and
        application roles. On repeat logins the full name is preserved unless it is
        blank.
        """

        normalized_email = email.strip().lower()
        user = self.get_by_email(normalized_email)
        if user is None:
            user = User(
                email=normalized_email,
                full_name=full_name.strip() or "Supabase User",
                hashed_password=None,
                auth_provider="supabase",
            )
            self._session.add(user)
            self._session.flush()
        else:
            user.auth_provider = "supabase"
            user.hashed_password = None
            if not user.full_name.strip():
                user.full_name = full_name.strip() or "Supabase User"
        self._session.commit()
        return user
