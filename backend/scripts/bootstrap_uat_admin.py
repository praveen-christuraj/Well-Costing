"""Create the first UAT administrator once without embedding or printing credentials.

This deployment helper is intentionally create-only. It refuses non-UAT environments and
non-empty user stores, and it never rotates an existing account's password.
"""

import os

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from sqlalchemy import func, select


def required(name: str) -> str:
    """Read a required non-empty environment variable."""

    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    """Create exactly one initial UAT administrator or make an existing account a no-op."""

    settings = get_settings()
    if settings.ENVIRONMENT != "uat":
        raise RuntimeError("UAT administrator bootstrap is allowed only when ENVIRONMENT=uat")

    email = required("BOOTSTRAP_ADMIN_EMAIL").strip().lower()
    password = required("BOOTSTRAP_ADMIN_PASSWORD")
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "UAT System Administrator").strip()
    if len(password) < 14:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 14 characters")
    if not full_name:
        raise RuntimeError("BOOTSTRAP_ADMIN_FULL_NAME cannot be blank")

    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"UAT administrator already exists; no changes made: {email}")
            return

        user_count = session.scalar(select(func.count()).select_from(User)) or 0
        if user_count != 0:
            raise RuntimeError(
                "UAT administrator bootstrap refused because the users table is not empty"
            )

        role = session.scalar(select(Role).where(Role.name == "admin"))
        if role is not None and not role.is_active:
            raise RuntimeError("UAT administrator bootstrap refused because admin role is inactive")
        if role is None:
            role = Role(name="admin", description="Bootstrap UAT System Administrator")
            session.add(role)

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            roles=[role],
        )
        session.add(user)
        session.commit()

    print(f"Created initial UAT administrator: {email}")


if __name__ == "__main__":
    main()
