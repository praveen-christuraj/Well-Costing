"""Add rigs, wells, well_sections and well_phases tables.

Revision ID: 20260827_0007
Revises: 20260827_0006
Create Date: 2026-08-28
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

revision: str = "20260827_0007"
down_revision: str | None = "20260827_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rigs
    create_table_if_missing(
        "rigs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rig_code", sa.String(length=50), nullable=False),
        sa.Column("rig_name", sa.String(length=200), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rigs")),
    )
    create_index_if_missing(op.f("ix_rigs_rig_code"), "rigs", ["rig_code"], unique=True)

    # Wells
    create_table_if_missing(
        "wells",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rig_id", sa.Integer(), nullable=False),
        sa.Column("well_code", sa.String(length=50), nullable=False),
        sa.Column("well_name", sa.String(length=200), nullable=False),
        sa.Column("well_location", sa.String(length=300), nullable=False),
        sa.Column("block", sa.String(length=200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("config_status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("depth_unit", sa.String(length=10), server_default="m", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["rig_id"], ["rigs.id"], name=op.f("fk_wells_rig_id_rigs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wells")),
    )
    create_index_if_missing(op.f("ix_wells_well_code"), "wells", ["well_code"], unique=True)
    create_index_if_missing(op.f("ix_wells_rig_id"), "wells", ["rig_id"], unique=False)
    create_index_if_missing(op.f("ix_wells_status"), "wells", ["status"], unique=False)
    create_index_if_missing(op.f("ix_wells_config_status"), "wells", ["config_status"], unique=False)

    # Well sections
    create_table_if_missing(
        "well_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("well_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("from_depth", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("to_depth", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], name=op.f("fk_well_sections_well_id_wells")),
        sa.ForeignKeyConstraint(["section_id"], ["hole_sections.id"], name=op.f("fk_well_sections_section_id_hole_sections")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_sections")),
    )
    create_index_if_missing(op.f("ix_well_sections_well_id"), "well_sections", ["well_id"], unique=False)
    create_index_if_missing(op.f("ix_well_sections_section_id"), "well_sections", ["section_id"], unique=False)

    # Well phases
    create_table_if_missing(
        "well_phases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("phase_id", sa.Integer(), nullable=False),
        sa.Column("days", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["well_sections.id"], name=op.f("fk_well_phases_section_id_well_sections")),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], name=op.f("fk_well_phases_phase_id_phases")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_phases")),
    )
    create_index_if_missing(op.f("ix_well_phases_section_id"), "well_phases", ["section_id"], unique=False)
    create_index_if_missing(op.f("ix_well_phases_phase_id"), "well_phases", ["phase_id"], unique=False)


def downgrade() -> None:
    drop_index_if_present(op.f("ix_well_phases_phase_id"), "well_phases")
    drop_index_if_present(op.f("ix_well_phases_section_id"), "well_phases")
    drop_table_if_present("well_phases")

    drop_index_if_present(op.f("ix_well_sections_section_id"), "well_sections")
    drop_index_if_present(op.f("ix_well_sections_well_id"), "well_sections")
    drop_table_if_present("well_sections")

    drop_index_if_present(op.f("ix_wells_config_status"), "wells")
    drop_index_if_present(op.f("ix_wells_status"), "wells")
    drop_index_if_present(op.f("ix_wells_rig_id"), "wells")
    drop_index_if_present(op.f("ix_wells_well_code"), "wells")
    drop_table_if_present("wells")

    drop_index_if_present(op.f("ix_rigs_rig_code"), "rigs")
    drop_table_if_present("rigs")
