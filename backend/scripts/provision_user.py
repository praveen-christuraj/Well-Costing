"""Provision or update a hosted user directly against the configured PostgreSQL database.

This is intentionally an out-of-band administration helper rather than an application endpoint.
Use it for Neon/Supabase-hosted environments when self-service signup is disabled.
"""

from __future__ import annotations

import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    email = required('PROVISION_USER_EMAIL').strip().lower()
    password = required('PROVISION_USER_PASSWORD')
    full_name = required('PROVISION_USER_FULL_NAME').strip()
    role_name = os.getenv('PROVISION_USER_ROLE', 'admin').strip().lower() or 'admin'

    if len(password) < 12:
        raise RuntimeError('PROVISION_USER_PASSWORD must contain at least 12 characters')
    if not full_name:
        raise RuntimeError('PROVISION_USER_FULL_NAME cannot be blank')

    with SessionLocal() as session:
        role = session.scalar(select(Role).where(Role.name == role_name))
        if role is not None and not role.is_active:
            raise RuntimeError(f'Cannot provision users with inactive role: {role_name}')
        if role is None:
            role = Role(name=role_name, description=f'Provisioned role: {role_name}')
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
            action = 'Created'
        else:
            user.full_name = full_name
            user.hashed_password = hash_password(password)
            user.is_active = True
            if role not in user.roles:
                user.roles.append(role)
            action = 'Updated'

        session.commit()

    print(f'{action} hosted user: {email} (role: {role_name})')


if __name__ == '__main__':
    main()