"""Add the Daily Cost tables (daily sheet + service / consumable / tangible lines).

Revision ID: 20260831_0010
Revises: 20260830_0009
Create Date: 2026-08-31

Daily costs are the operational counterpart of the AFE and are **completely
well scoped**: ``daily_cost_entries`` hangs off one rig + well + date
(``(well_id, cost_date)`` is unique, one sheet per day) and owns three kinds of
line — services (priced from the AFE rate card per charging basis and charge
category), consumables (mud chemicals, fuel, cement additives, drill bits) and
tangibles.

Every line stores its **scope** (``section_id`` / ``phase_id`` from Master Data
hole sections / phases, ``sub_activity_id`` from the well's sub activities) and
its ``captured_rate`` / ``override_rate`` pair, plus the ``amount`` the engine
priced — so reports and analytics read stored figures instead of recomputing
history.

The entries also carry the **reconciliation** middle layer up front
(``reconciliation_status``, ``reconciliation_ref``, ``reconciled_at``,
``reconciled_by``): actual cost is captured daily but reconciled weekly — or
whenever required — before it is compared with the AFE, so the daily module
writes ``pending`` and the reconciliation module that lands later stamps the
rest without needing another migration.
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

revision: str = "20260831_0010"
down_revision: str | None = "20260830_0009"
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
        "daily_cost_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("daily_cost_code", sa.String(length=80), nullable=False),
        sa.Column("rig_id", sa.Integer(), nullable=False),
        sa.Column("well_id", sa.Integer(), nullable=False),
        sa.Column("cost_date", sa.Date(), nullable=False),
        sa.Column("afe_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reconciliation_status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("reconciliation_ref", sa.String(length=50), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["rig_id"], ["rigs.id"], name=op.f("fk_daily_cost_entries_rig_id_rigs")),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], name=op.f("fk_daily_cost_entries_well_id_wells")),
        sa.ForeignKeyConstraint(["afe_id"], ["afes.id"], name=op.f("fk_daily_cost_entries_afe_id_afes")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_cost_entries")),
        sa.UniqueConstraint("daily_cost_code", name=op.f("uq_daily_cost_entries_daily_cost_code")),
        sa.UniqueConstraint("well_id", "cost_date", name=op.f("uq_daily_cost_entries_well_date")),
    )
    for index, columns in (
        ("ix_daily_cost_entries_daily_cost_code", ["daily_cost_code"]),
        ("ix_daily_cost_entries_rig_id", ["rig_id"]),
        ("ix_daily_cost_entries_well_id", ["well_id"]),
        ("ix_daily_cost_entries_cost_date", ["cost_date"]),
        ("ix_daily_cost_entries_afe_id", ["afe_id"]),
        ("ix_daily_cost_entries_status", ["status"]),
        ("ix_daily_cost_entries_reconciliation_status", ["reconciliation_status"]),
        ("ix_daily_cost_entries_is_deleted", ["is_deleted"]),
    ):
        create_index_if_missing(op.f(index), "daily_cost_entries", columns, unique=False)

    create_table_if_missing(
        "daily_cost_service_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("afe_line_id", sa.Integer(), nullable=True),
        sa.Column("charging_basis", sa.String(length=30), nullable=False),
        sa.Column("charge_category", sa.String(length=40), server_default="Operation", nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("phase_id", sa.Integer(), nullable=True),
        sa.Column("sub_activity_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), server_default="0", nullable=False),
        sa.Column("quantity_unit", sa.String(length=10), server_default="hours", nullable=False),
        sa.Column("captured_rate", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("override_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["entry_id"], ["daily_cost_entries.id"],
            name=op.f("fk_daily_cost_service_lines_entry_id_daily_cost_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_daily_cost_service_lines_service_id_services")
        ),
        sa.ForeignKeyConstraint(
            ["afe_line_id"], ["afe_service_lines.id"],
            name=op.f("fk_daily_cost_service_lines_afe_line_id_afe_service_lines"),
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["hole_sections.id"],
            name=op.f("fk_daily_cost_service_lines_section_id_hole_sections"),
        ),
        sa.ForeignKeyConstraint(
            ["phase_id"], ["phases.id"], name=op.f("fk_daily_cost_service_lines_phase_id_phases")
        ),
        sa.ForeignKeyConstraint(
            ["sub_activity_id"], ["well_sub_activities.id"],
            name=op.f("fk_daily_cost_service_lines_sub_activity_id_well_sub_activities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_cost_service_lines")),
    )
    for index, columns in (
        ("ix_daily_cost_service_lines_entry_id", ["entry_id"]),
        ("ix_daily_cost_service_lines_service_id", ["service_id"]),
        ("ix_daily_cost_service_lines_afe_line_id", ["afe_line_id"]),
        ("ix_daily_cost_service_lines_section_id", ["section_id"]),
        ("ix_daily_cost_service_lines_phase_id", ["phase_id"]),
        ("ix_daily_cost_service_lines_sub_activity_id", ["sub_activity_id"]),
    ):
        create_index_if_missing(op.f(index), "daily_cost_service_lines", columns, unique=False)

    create_table_if_missing(
        "daily_cost_consumable_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_code", sa.String(length=50), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), server_default="0", nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("captured_rate", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("override_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("manual_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("phase_id", sa.Integer(), nullable=True),
        sa.Column("sub_activity_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["entry_id"], ["daily_cost_entries.id"],
            name=op.f("fk_daily_cost_consumable_lines_entry_id_daily_cost_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["hole_sections.id"],
            name=op.f("fk_daily_cost_consumable_lines_section_id_hole_sections"),
        ),
        sa.ForeignKeyConstraint(
            ["phase_id"], ["phases.id"], name=op.f("fk_daily_cost_consumable_lines_phase_id_phases")
        ),
        sa.ForeignKeyConstraint(
            ["sub_activity_id"], ["well_sub_activities.id"],
            name=op.f("fk_daily_cost_consumable_lines_sub_activity_id_well_sub_activities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_cost_consumable_lines")),
    )
    for index, columns in (
        ("ix_daily_cost_consumable_lines_entry_id", ["entry_id"]),
        ("ix_daily_cost_consumable_lines_category", ["category"]),
        ("ix_daily_cost_consumable_lines_item_id", ["item_id"]),
        ("ix_daily_cost_consumable_lines_section_id", ["section_id"]),
        ("ix_daily_cost_consumable_lines_phase_id", ["phase_id"]),
        ("ix_daily_cost_consumable_lines_sub_activity_id", ["sub_activity_id"]),
    ):
        create_index_if_missing(op.f(index), "daily_cost_consumable_lines", columns, unique=False)

    create_table_if_missing(
        "daily_cost_tangible_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("tangible_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), server_default="1", nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("captured_rate", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("override_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["entry_id"], ["daily_cost_entries.id"],
            name=op.f("fk_daily_cost_tangible_lines_entry_id_daily_cost_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["tangible_id"], ["tangibles.id"],
            name=op.f("fk_daily_cost_tangible_lines_tangible_id_tangibles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_cost_tangible_lines")),
    )
    for index, columns in (
        ("ix_daily_cost_tangible_lines_entry_id", ["entry_id"]),
        ("ix_daily_cost_tangible_lines_tangible_id", ["tangible_id"]),
    ):
        create_index_if_missing(op.f(index), "daily_cost_tangible_lines", columns, unique=False)


def downgrade() -> None:
    for index in (
        "ix_daily_cost_tangible_lines_tangible_id",
        "ix_daily_cost_tangible_lines_entry_id",
    ):
        drop_index_if_present(op.f(index), "daily_cost_tangible_lines")
    drop_table_if_present("daily_cost_tangible_lines")

    for index in (
        "ix_daily_cost_consumable_lines_sub_activity_id",
        "ix_daily_cost_consumable_lines_phase_id",
        "ix_daily_cost_consumable_lines_section_id",
        "ix_daily_cost_consumable_lines_item_id",
        "ix_daily_cost_consumable_lines_category",
        "ix_daily_cost_consumable_lines_entry_id",
    ):
        drop_index_if_present(op.f(index), "daily_cost_consumable_lines")
    drop_table_if_present("daily_cost_consumable_lines")

    for index in (
        "ix_daily_cost_service_lines_sub_activity_id",
        "ix_daily_cost_service_lines_phase_id",
        "ix_daily_cost_service_lines_section_id",
        "ix_daily_cost_service_lines_afe_line_id",
        "ix_daily_cost_service_lines_service_id",
        "ix_daily_cost_service_lines_entry_id",
    ):
        drop_index_if_present(op.f(index), "daily_cost_service_lines")
    drop_table_if_present("daily_cost_service_lines")

    for index in (
        "ix_daily_cost_entries_is_deleted",
        "ix_daily_cost_entries_reconciliation_status",
        "ix_daily_cost_entries_status",
        "ix_daily_cost_entries_afe_id",
        "ix_daily_cost_entries_cost_date",
        "ix_daily_cost_entries_well_id",
        "ix_daily_cost_entries_rig_id",
        "ix_daily_cost_entries_daily_cost_code",
    ):
        drop_index_if_present(op.f(index), "daily_cost_entries")
    drop_table_if_present("daily_cost_entries")
