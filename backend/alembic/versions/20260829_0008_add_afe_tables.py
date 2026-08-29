"""Add the AFE tables (AFE header + cost estimation lines).

Revision ID: 20260829_0008
Revises: 20260827_0007
Create Date: 2026-08-29

An AFE is well-scoped: ``afes`` hangs off one rig + well pair and carries the
draft / submitted / approved status. Its cost estimation lives in the child
tables — one row per configured service / consumable / tangible, plus the
service rate card, the day-based charge lines and the per-section rates.

Section and phase references point at the **master data** ids
(``hole_sections`` / ``phases``) rather than at ``well_sections`` rows, because
saving a well configuration replaces those rows wholesale; the stable master
ids keep an AFE's scope valid across well-configuration re-saves.
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

revision: str = "20260829_0008"
down_revision: str | None = "20260827_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_COLUMNS = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=True),
    sa.Column("updated_by", sa.Uuid(), nullable=True),
)


def upgrade() -> None:
    # AFE header -----------------------------------------------------------
    create_table_if_missing(
        "afes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("afe_code", sa.String(length=50), nullable=False),
        sa.Column("afe_name", sa.String(length=200), nullable=False),
        sa.Column("afe_type", sa.String(length=20), nullable=False),
        sa.Column("rig_id", sa.Integer(), nullable=False),
        sa.Column("well_id", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("status_remarks", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["rig_id"], ["rigs.id"], name=op.f("fk_afes_rig_id_rigs")),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], name=op.f("fk_afes_well_id_wells")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afes")),
    )
    create_index_if_missing(op.f("ix_afes_afe_code"), "afes", ["afe_code"], unique=True)
    create_index_if_missing(op.f("ix_afes_afe_type"), "afes", ["afe_type"], unique=False)
    create_index_if_missing(op.f("ix_afes_rig_id"), "afes", ["rig_id"], unique=False)
    create_index_if_missing(op.f("ix_afes_well_id"), "afes", ["well_id"], unique=False)
    create_index_if_missing(op.f("ix_afes_status"), "afes", ["status"], unique=False)

    # Service lines --------------------------------------------------------
    create_table_if_missing(
        "afe_service_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("afe_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("charging_basis", sa.String(length=30), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("phase_id", sa.Integer(), nullable=True),
        sa.Column("per_service_amount", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["afe_id"], ["afes.id"], name=op.f("fk_afe_service_lines_afe_id_afes")),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], name=op.f("fk_afe_service_lines_service_id_services")),
        sa.ForeignKeyConstraint(["section_id"], ["hole_sections.id"], name=op.f("fk_afe_service_lines_section_id_hole_sections")),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], name=op.f("fk_afe_service_lines_phase_id_phases")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_service_lines")),
    )
    create_index_if_missing(op.f("ix_afe_service_lines_afe_id"), "afe_service_lines", ["afe_id"], unique=False)
    create_index_if_missing(op.f("ix_afe_service_lines_service_id"), "afe_service_lines", ["service_id"], unique=False)
    create_index_if_missing(op.f("ix_afe_service_lines_section_id"), "afe_service_lines", ["section_id"], unique=False)
    create_index_if_missing(op.f("ix_afe_service_lines_phase_id"), "afe_service_lines", ["phase_id"], unique=False)

    # Service rate card ----------------------------------------------------
    create_table_if_missing(
        "afe_service_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("unit_rate", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["line_id"], ["afe_service_lines.id"], name=op.f("fk_afe_service_rates_line_id_afe_service_lines")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_service_rates")),
        sa.UniqueConstraint(
            "line_id", "category", name=op.f("uq_afe_service_rates_line_category")
        ),
    )
    create_index_if_missing(op.f("ix_afe_service_rates_line_id"), "afe_service_rates", ["line_id"], unique=False)

    # Day-based charge lines ----------------------------------------------
    create_table_if_missing(
        "afe_service_charge_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), server_default="0", nullable=False),
        sa.Column("quantity_unit", sa.String(length=10), server_default="days", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["afe_service_lines.id"],
            name=op.f("fk_afe_service_charge_lines_line_id_afe_service_lines"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_service_charge_lines")),
    )
    create_index_if_missing(
        op.f("ix_afe_service_charge_lines_line_id"), "afe_service_charge_lines", ["line_id"], unique=False
    )

    # Per-section rates ----------------------------------------------------
    create_table_if_missing(
        "afe_service_section_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("phase_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["afe_service_lines.id"],
            name=op.f("fk_afe_service_section_rates_line_id_afe_service_lines"),
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["hole_sections.id"],
            name=op.f("fk_afe_service_section_rates_section_id_hole_sections"),
        ),
        sa.ForeignKeyConstraint(
            ["phase_id"], ["phases.id"], name=op.f("fk_afe_service_section_rates_phase_id_phases")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_service_section_rates")),
    )
    create_index_if_missing(
        op.f("ix_afe_service_section_rates_line_id"), "afe_service_section_rates", ["line_id"], unique=False
    )
    create_index_if_missing(
        op.f("ix_afe_service_section_rates_section_id"), "afe_service_section_rates", ["section_id"], unique=False
    )
    create_index_if_missing(
        op.f("ix_afe_service_section_rates_phase_id"), "afe_service_section_rates", ["phase_id"], unique=False
    )

    # Consumable lines -----------------------------------------------------
    create_table_if_missing(
        "afe_consumable_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("afe_id", sa.Integer(), nullable=False),
        sa.Column("item_kind", sa.String(length=20), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(length=50), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), server_default="1", nullable=False),
        sa.Column("captured_rate", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("override_rate", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("phase_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["afe_id"], ["afes.id"], name=op.f("fk_afe_consumable_lines_afe_id_afes")),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["hole_sections.id"],
            name=op.f("fk_afe_consumable_lines_section_id_hole_sections"),
        ),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], name=op.f("fk_afe_consumable_lines_phase_id_phases")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_consumable_lines")),
    )
    create_index_if_missing(op.f("ix_afe_consumable_lines_afe_id"), "afe_consumable_lines", ["afe_id"], unique=False)
    create_index_if_missing(op.f("ix_afe_consumable_lines_item_id"), "afe_consumable_lines", ["item_id"], unique=False)
    create_index_if_missing(
        op.f("ix_afe_consumable_lines_section_id"), "afe_consumable_lines", ["section_id"], unique=False
    )
    create_index_if_missing(op.f("ix_afe_consumable_lines_phase_id"), "afe_consumable_lines", ["phase_id"], unique=False)

    # Tangible lines -------------------------------------------------------
    create_table_if_missing(
        "afe_tangible_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("afe_id", sa.Integer(), nullable=False),
        sa.Column("tangible_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), server_default="1", nullable=False),
        sa.Column("captured_rate", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("override_rate", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *TIMESTAMP_COLUMNS,
        sa.ForeignKeyConstraint(["afe_id"], ["afes.id"], name=op.f("fk_afe_tangible_lines_afe_id_afes")),
        sa.ForeignKeyConstraint(
            ["tangible_id"], ["tangibles.id"], name=op.f("fk_afe_tangible_lines_tangible_id_tangibles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afe_tangible_lines")),
    )
    create_index_if_missing(op.f("ix_afe_tangible_lines_afe_id"), "afe_tangible_lines", ["afe_id"], unique=False)
    create_index_if_missing(op.f("ix_afe_tangible_lines_tangible_id"), "afe_tangible_lines", ["tangible_id"], unique=False)


def downgrade() -> None:
    drop_index_if_present(op.f("ix_afe_tangible_lines_tangible_id"), "afe_tangible_lines")
    drop_index_if_present(op.f("ix_afe_tangible_lines_afe_id"), "afe_tangible_lines")
    drop_table_if_present("afe_tangible_lines")

    drop_index_if_present(op.f("ix_afe_consumable_lines_phase_id"), "afe_consumable_lines")
    drop_index_if_present(op.f("ix_afe_consumable_lines_section_id"), "afe_consumable_lines")
    drop_index_if_present(op.f("ix_afe_consumable_lines_item_id"), "afe_consumable_lines")
    drop_index_if_present(op.f("ix_afe_consumable_lines_afe_id"), "afe_consumable_lines")
    drop_table_if_present("afe_consumable_lines")

    drop_index_if_present(op.f("ix_afe_service_section_rates_phase_id"), "afe_service_section_rates")
    drop_index_if_present(op.f("ix_afe_service_section_rates_section_id"), "afe_service_section_rates")
    drop_index_if_present(op.f("ix_afe_service_section_rates_line_id"), "afe_service_section_rates")
    drop_table_if_present("afe_service_section_rates")

    drop_index_if_present(op.f("ix_afe_service_charge_lines_line_id"), "afe_service_charge_lines")
    drop_table_if_present("afe_service_charge_lines")

    drop_index_if_present(op.f("ix_afe_service_rates_line_id"), "afe_service_rates")
    drop_table_if_present("afe_service_rates")

    drop_index_if_present(op.f("ix_afe_service_lines_phase_id"), "afe_service_lines")
    drop_index_if_present(op.f("ix_afe_service_lines_section_id"), "afe_service_lines")
    drop_index_if_present(op.f("ix_afe_service_lines_service_id"), "afe_service_lines")
    drop_index_if_present(op.f("ix_afe_service_lines_afe_id"), "afe_service_lines")
    drop_table_if_present("afe_service_lines")

    drop_index_if_present(op.f("ix_afes_status"), "afes")
    drop_index_if_present(op.f("ix_afes_well_id"), "afes")
    drop_index_if_present(op.f("ix_afes_rig_id"), "afes")
    drop_index_if_present(op.f("ix_afes_afe_type"), "afes")
    drop_index_if_present(op.f("ix_afes_afe_code"), "afes")
    drop_table_if_present("afes")
