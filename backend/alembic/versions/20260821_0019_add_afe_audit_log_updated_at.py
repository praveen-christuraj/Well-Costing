"""Add the missing updated_at column to afe_audit_logs.

Migration 0018 created ``afe_audit_logs`` with ``created_at`` only, while the
``AfeAuditLog`` model carries the full ``TimestampMixin`` (``created_at`` and
``updated_at``). Because ``Afe.audit_logs`` is eagerly loaded by every AFE
query, the absent column made the AFE, well, project, and estimate list
endpoints fail with ``column afe_audit_logs.updated_at does not exist`` on
any database where 0018 had already been applied.

Revision ID: 20260821_0019
Revises: 20260821_0018
Create Date: 2026-08-21 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0019"
down_revision: str | None = "20260821_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "afe_audit_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("afe_audit_logs") as batch:
            batch.drop_column("updated_at")
    else:
        op.drop_column("afe_audit_logs", "updated_at")
