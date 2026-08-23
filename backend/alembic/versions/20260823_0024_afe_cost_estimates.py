"""Create the AFE cost estimate rate table.

One row per AFE line holding the well-scoped unit rate. The AFE Cost
Estimates page writes these rows; daily cost entries read their default unit
rates from here (with a per-line override recorded on the entry).

Revision ID: 20260823_0024
Revises: 20260823_0023
Create Date: 2026-08-23 10:00:00.000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0024"
down_revision: str | None = "20260823_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "afe_cost_estimate_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("afe_id", sa.Uuid(), nullable=False),
        sa.Column("afe_line_id", sa.Uuid(), nullable=False),
        sa.Column("unit_rate", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["afe_id"], ["afes.id"], ondelete="CASCADE",
            name="fk_afe_cost_estimate_lines_afe_id",
        ),
        sa.ForeignKeyConstraint(
            ["afe_line_id"], ["afe_lines.id"], ondelete="CASCADE",
            name="fk_afe_cost_estimate_lines_afe_line_id",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.id"], ondelete="RESTRICT",
            name="fk_afe_cost_estimate_lines_vendor_id",
        ),
        sa.UniqueConstraint("afe_line_id", name="uq_afe_cost_estimate_lines_afe_line"),
        sa.CheckConstraint("unit_rate >= 0", name="non_negative_estimate_unit_rate"),
    )
    op.create_index(
        "ix_afe_cost_estimate_lines_afe_id", "afe_cost_estimate_lines", ["afe_id"]
    )
    op.create_index(
        "ix_afe_cost_estimate_lines_afe_line_id", "afe_cost_estimate_lines", ["afe_line_id"]
    )
    op.create_index(
        "ix_afe_cost_estimate_lines_vendor_id", "afe_cost_estimate_lines", ["vendor_id"]
    )
    op.create_index(
        "ix_afe_cost_estimate_lines_is_active", "afe_cost_estimate_lines", ["is_active"]
    )


def downgrade() -> None:
    op.drop_index("ix_afe_cost_estimate_lines_is_active", table_name="afe_cost_estimate_lines")
    op.drop_index("ix_afe_cost_estimate_lines_vendor_id", table_name="afe_cost_estimate_lines")
    op.drop_index("ix_afe_cost_estimate_lines_afe_line_id", table_name="afe_cost_estimate_lines")
    op.drop_index("ix_afe_cost_estimate_lines_afe_id", table_name="afe_cost_estimate_lines")
    op.drop_table("afe_cost_estimate_lines")
