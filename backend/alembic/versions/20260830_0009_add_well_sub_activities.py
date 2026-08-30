"""Add the Well Sub Activities table.

Revision ID: 20260830_0009
Revises: 20260829_0008
Create Date: 2026-08-30

Well sub activities are **completely well scoped**: ``well_sub_activities``
hangs off one well and distributes the master-data Activities to the
responsible parties / companies executing them. ``sub_activity_code`` is a
manual code that must never be duplicated *within the same well* — the same
code may still be used on another well — so uniqueness is a composite
``(well_id, sub_activity_code)`` constraint rather than a global one.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.migration_ops import (
    create_index_if_missing,
    create_table_if_missing,
    drop_index_if_present,
    drop_table_if_present,
)

revision: str = "20260830_0009"
down_revision: str | None = "20260829_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_COLUMNS = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=True),
    sa.Column("updated_by", sa.Uuid(), nullable=True),
)


def upgrade() -> None:
    create_table_if_missing(
        "well_sub_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("well_id", sa.Integer(), nullable=False),
        sa.Column("sub_activity_code", sa.String(length=50), nullable=False),
        sa.Column("sub_activity_name", sa.String(length=150), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("responsible_party", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["well_id"], ["wells.id"], name=op.f("fk_well_sub_activities_well_id_wells")
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], name=op.f("fk_well_sub_activities_activity_id_activities")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_sub_activities")),
        sa.UniqueConstraint(
            "well_id", "sub_activity_code", name=op.f("uq_well_sub_activities_well_code")
        ),
    )
    create_index_if_missing(
        op.f("ix_well_sub_activities_well_id"), "well_sub_activities", ["well_id"], unique=False
    )
    create_index_if_missing(
        op.f("ix_well_sub_activities_activity_id"), "well_sub_activities", ["activity_id"], unique=False
    )
    create_index_if_missing(
        op.f("ix_well_sub_activities_is_deleted"), "well_sub_activities", ["is_deleted"], unique=False
    )


def downgrade() -> None:
    drop_index_if_present(op.f("ix_well_sub_activities_is_deleted"), "well_sub_activities")
    drop_index_if_present(op.f("ix_well_sub_activities_activity_id"), "well_sub_activities")
    drop_index_if_present(op.f("ix_well_sub_activities_well_id"), "well_sub_activities")
    drop_table_if_present("well_sub_activities")
