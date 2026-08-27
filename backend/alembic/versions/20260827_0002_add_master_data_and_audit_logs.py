"""Add master data and audit logs tables.

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Unit of Measurements
    op.create_table(
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
    op.create_index(op.f("ix_uom_unit_code"), "uom", ["unit_code"], unique=True)

    # Currencies
    op.create_table(
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
    op.create_index(op.f("ix_currencies_currency_code"), "currencies", ["currency_code"], unique=True)

    # Phases
    op.create_table(
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
    op.create_index(op.f("ix_phases_phase_code"), "phases", ["phase_code"], unique=True)

    # Activities
    op.create_table(
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
    op.create_index(op.f("ix_activities_activity_code"), "activities", ["activity_code"], unique=True)

    # Hole Sections
    op.create_table(
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
    op.create_index(op.f("ix_hole_sections_section_code"), "hole_sections", ["section_code"], unique=True)

    # Audit Logs
    op.create_table(
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
    op.create_index(op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_email"), "audit_logs", ["user_email"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_module"), "audit_logs", ["module"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_code"), "audit_logs", ["entity_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_entity_code"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_module"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_email"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_timestamp"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_hole_sections_section_code"), table_name="hole_sections")
    op.drop_table("hole_sections")

    op.drop_index(op.f("ix_activities_activity_code"), table_name="activities")
    op.drop_table("activities")

    op.drop_index(op.f("ix_phases_phase_code"), table_name="phases")
    op.drop_table("phases")

    op.drop_index(op.f("ix_currencies_currency_code"), table_name="currencies")
    op.drop_table("currencies")

    op.drop_index(op.f("ix_uom_unit_code"), table_name="uom")
    op.drop_table("uom")
