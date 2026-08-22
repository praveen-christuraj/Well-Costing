"""Add soft-delete columns to cost estimates.

Revision ID: 20260822_0021
Revises: 20260821_0020
Create Date: 2026-08-22 09:00:00.000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0021"
down_revision: str | None = "20260821_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cost_estimates",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("cost_estimates", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.add_column(
        "cost_estimates",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index("ix_cost_estimates_is_active", "cost_estimates", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_cost_estimates_is_active", table_name="cost_estimates")
    op.drop_column("cost_estimates", "is_active")
    op.drop_column("cost_estimates", "deleted_by")
    op.drop_column("cost_estimates", "deleted_at")
