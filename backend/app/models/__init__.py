"""SQLAlchemy model exports used by Alembic metadata discovery.

The application was restructured down to its authentication foundation, so
users and roles are the only persisted entities.
"""

from app.models.role import Role
from app.models.user import User, user_roles

__all__ = [
    "Role",
    "User",
    "user_roles",
]
