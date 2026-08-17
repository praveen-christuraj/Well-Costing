"""Allow Supabase Auth identities to sign in without a local password hash.

Revision ID: 20260816_0013
Revises: 20260814_0012
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0013"
down_revision: str | None = "20260814_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every existing row keeps its local-password behaviour; new Supabase users
    # are added with auth_provider="supabase" and no hashed_password.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auth_provider",
                sa.String(length=20),
                nullable=False,
                server_default="local",
            )
        )
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    # Fill any NULL password hashes with a value that can never verify so the
    # column can return to NOT NULL even if a Supabase user was mirrored.
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.drop_column("auth_provider")
