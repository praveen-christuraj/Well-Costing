"""Create or update a local/CI user from environment variables.

This script never contains or prints a password. It is not an application endpoint.
"""

import os

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from sqlalchemy import select


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    email = required("SEED_USER_EMAIL").strip().lower()
    password = required("SEED_USER_PASSWORD")
    full_name = os.getenv("SEED_USER_FULL_NAME", "Development Administrator").strip()
    if len(password) < 12:
        raise RuntimeError("SEED_USER_PASSWORD must contain at least 12 characters")

    with SessionLocal() as session:
        role = session.scalar(select(Role).where(Role.name == "admin"))
        if role is None:
            role = Role(name="admin", description="Development/CI administrator")
            session.add(role)
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                roles=[role],
            )
            session.add(user)
        else:
            user.full_name = full_name
            user.hashed_password = hash_password(password)
            user.is_active = True
            if role not in user.roles:
                user.roles.append(role)
        session.commit()
    print(f"Seeded development user: {email}")


if __name__ == "__main__":
    main()
