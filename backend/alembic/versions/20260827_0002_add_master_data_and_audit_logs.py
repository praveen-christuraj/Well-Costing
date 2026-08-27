"""Add master data and audit logs tables.

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27
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

revision: str = "20260827_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Unit of Measurements
    create_table_if_missing(
        "uom",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unit_code", sa.String(length=50), nullable=False),
        sa.Column("unit_name", sa.String(length=150), nullable=False),
        sa.Column("unit_symbol", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uom")),
    )
    create_index_if_missing(op.f("ix_uom_unit_code"), "uom", ["unit_code"], unique=True)

    # Currencies
    create_table_if_missing(
        "currencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency_code", sa.String(length=10), nullable=False),
        sa.Column("currency_name", sa.String(length=100), nullable=False),
        sa.Column("currency_symbol", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_currencies")),
    )
    create_index_if_missing(op.f("ix_currencies_currency_code"), "currencies", ["currency_code"], unique=True)

    # Phases
    create_table_if_missing(
        "phases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phase_code", sa.String(length=50), nullable=False),
        sa.Column("phase_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phases")),
    )
    create_index_if_missing(op.f("ix_phases_phase_code"), "phases", ["phase_code"], unique=True)

    # Activities
    create_table_if_missing(
        "activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_code", sa.String(length=50), nullable=False),
        sa.Column("activity_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activities")),
    )
    create_index_if_missing(op.f("ix_activities_activity_code"), "activities", ["activity_code"], unique=True)

    # Hole Sections
    create_table_if_missing(
        "hole_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("section_code", sa.String(length=50), nullable=False),
        sa.Column("section_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hole_sections")),
    )
    create_index_if_missing(op.f("ix_hole_sections_section_code"), "hole_sections", ["section_code"], unique=True)

    # Audit Logs
    create_table_if_missing(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_email", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("entity_code", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    create_index_if_missing(op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False)
    create_index_if_missing(op.f("ix_audit_logs_user_email"), "audit_logs", ["user_email"], unique=False)
    create_index_if_missing(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    create_index_if_missing(op.f("ix_audit_logs_module"), "audit_logs", ["module"], unique=False)
    create_index_if_missing(op.f("ix_audit_logs_entity_code"), "audit_logs", ["entity_code"], unique=False)


def downgrade() -> None:
    drop_index_if_present(op.f("ix_audit_logs_entity_code"), "audit_logs")
    drop_index_if_present(op.f("ix_audit_logs_module"), "audit_logs")
    drop_index_if_present(op.f("ix_audit_logs_action"), "audit_logs")
    drop_index_if_present(op.f("ix_audit_logs_user_email"), "audit_logs")
    drop_index_if_present(op.f("ix_audit_logs_timestamp"), "audit_logs")
    drop_table_if_present("audit_logs")

    drop_index_if_present(op.f("ix_hole_sections_section_code"), "hole_sections")
    drop_table_if_present("hole_sections")

    drop_index_if_present(op.f("ix_activities_activity_code"), "activities")
    drop_table_if_present("activities")

    drop_index_if_present(op.f("ix_phases_phase_code"), "phases")
    drop_table_if_present("phases")

    drop_index_if_present(op.f("ix_currencies_currency_code"), "currencies")
    drop_table_if_present("currencies")

    drop_index_if_present(op.f("ix_uom_unit_code"), "uom")
    drop_table_if_present("uom")
