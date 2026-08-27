"""Create or update a local/CI user from environment variables.

This script never contains or prints a password. It is not an application endpoint.
"""

import os
import sys
from pathlib import Path

# Allow running as `python scripts/seed_user.py` from any directory: Python only
# puts the script's own folder (backend/scripts) on sys.path, so point at the
# backend root to make `app` importable without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from sqlalchemy import select


def load_backend_env() -> None:
    """Load backend/.env values into os.environ if not already set."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key.startswith("export "):
                        key = key[7:].strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    load_backend_env()
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
