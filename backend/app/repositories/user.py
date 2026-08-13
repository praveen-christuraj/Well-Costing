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
