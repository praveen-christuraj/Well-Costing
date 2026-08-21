"""Add AFE reopening audit, AFE section breakdown, configurable phases, and daily cost tracking.

Revision ID: 20260821_0018
Revises: 20260821_0017
Create Date: 2026-08-21 12:00:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0018"
down_revision: str | None = "20260821_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    # 1. Add fields to afes
    op.add_column(
        "afes",
        sa.Column(
            "budget_amount",
            sa.Numeric(18, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "total_planned_days",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "total_planned_depth",
            sa.Numeric(14, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "depth_unit_id",
            sa.UUID(),
            sa.ForeignKey("units.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "reopen_remarks",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "reopened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "afes",
        sa.Column(
            "reopened_by",
            sa.UUID(),
            nullable=True,
        ),
    )

    # 2. Create drilling_phases
    op.create_table(
        "drilling_phases",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
    )

    # Seed initial standard drilling phases
    phases_table = sa.table(
        "drilling_phases",
        sa.column("id", sa.UUID),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("sequence", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    default_phases = [
        {"id": uuid4(), "code": "DRILL", "name": "Drilling", "description": "Hole drilling operations", "sequence": 1, "is_active": True},
        {"id": uuid4(), "code": "LOG", "name": "Logging", "description": "Wireline and formation evaluation logging", "sequence": 2, "is_active": True},
        {"id": uuid4(), "code": "CAS_CEM", "name": "Casing & Cementing", "description": "Running casing and primary cementing", "sequence": 3, "is_active": True},
        {"id": uuid4(), "code": "COMP", "name": "Completion", "description": "Lower and upper completion operations", "sequence": 4, "is_active": True},
        {"id": uuid4(), "code": "TEST", "name": "Well Testing", "description": "Flow testing and well cleanup", "sequence": 5, "is_active": True},
        {"id": uuid4(), "code": "MOB", "name": "Mobilisation & Rig Move", "description": "Rig move, positioning, and rig up", "sequence": 6, "is_active": True},
        {"id": uuid4(), "code": "ABAN", "name": "Plug & Abandonment", "description": "Well plugging and decommissioning", "sequence": 7, "is_active": True},
    ]
    op.bulk_insert(phases_table, default_phases)

    # 3. Create afe_sections
    op.create_table(
        "afe_sections",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("afe_id", sa.UUID(), sa.ForeignKey("afes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hole_section_id", sa.UUID(), sa.ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("phase", sa.String(100), nullable=False, server_default="Drilling", index=True),
        sa.Column("planned_days", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("planned_depth_from", sa.Numeric(14, 4), nullable=True),
        sa.Column("planned_depth_to", sa.Numeric(14, 4), nullable=True),
        sa.Column("depth_unit_id", sa.UUID(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("sequence >= 1", name="positive_afe_section_sequence"),
        sa.CheckConstraint("planned_days >= 0", name="non_negative_afe_section_days"),
    )

    # 4. Create afe_audit_logs
    op.create_table(
        "afe_audit_logs",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("afe_id", sa.UUID(), sa.ForeignKey("afes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=False, index=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 5. Create daily_cost_entries
    op.create_table(
        "daily_cost_entries",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("well_id", sa.UUID(), sa.ForeignKey("wells.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("afe_id", sa.UUID(), sa.ForeignKey("afes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("entry_date", sa.Date(), nullable=False, index=True),
        sa.Column("hole_section_id", sa.UUID(), sa.ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("phase", sa.String(100), nullable=True, index=True),
        sa.Column("current_depth", sa.Numeric(14, 4), nullable=True),
        sa.Column("daily_progress", sa.Numeric(14, 4), nullable=True),
        sa.Column("operational_summary", sa.Text(), nullable=True),
        sa.Column("total_services_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_consumables_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_daily_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cumulative_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.UniqueConstraint("well_id", "entry_date", name="uq_daily_cost_entries_well_date"),
    )

    # 6. Create daily_cost_service_lines
    op.create_table(
        "daily_cost_service_lines",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("daily_cost_entry_id", sa.UUID(), sa.ForeignKey("daily_cost_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("service_id", sa.UUID(), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("cost_code_id", sa.UUID(), sa.ForeignKey("cost_codes.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("vendor_id", sa.UUID(), sa.ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("hole_section_id", sa.UUID(), sa.ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("service_hours", sa.Numeric(8, 2), nullable=False, server_default="24.0"),
        sa.Column("operating_days", sa.Numeric(10, 4), nullable=False, server_default="1.0"),
        sa.Column("rate_basis", sa.String(20), nullable=False, server_default="daily", index=True),
        sa.Column("unit_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("service_hours >= 0 AND service_hours <= 24", name="valid_service_hours"),
        sa.CheckConstraint("operating_days >= 0", name="non_negative_operating_days"),
        sa.CheckConstraint("unit_rate >= 0", name="non_negative_service_unit_rate"),
        sa.CheckConstraint("amount >= 0", name="non_negative_service_amount"),
    )

    # 7. Create daily_cost_consumable_lines
    op.create_table(
        "daily_cost_consumable_lines",
        sa.Column("id", sa.UUID(), primary_key=True, default=uuid4),
        sa.Column("daily_cost_entry_id", sa.UUID(), sa.ForeignKey("daily_cost_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("consumable_id", sa.UUID(), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("cost_code_id", sa.UUID(), sa.ForeignKey("cost_codes.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("vendor_id", sa.UUID(), sa.ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit_id", sa.UUID(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("unit_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("quantity >= 0", name="non_negative_consumable_quantity"),
        sa.CheckConstraint("unit_rate >= 0", name="non_negative_consumable_unit_rate"),
        sa.CheckConstraint("amount >= 0", name="non_negative_consumable_amount"),
    )


def downgrade() -> None:
    op.drop_table("daily_cost_consumable_lines")
    op.drop_table("daily_cost_service_lines")
    op.drop_table("daily_cost_entries")
    op.drop_table("afe_audit_logs")
    op.drop_table("afe_sections")
    op.drop_table("drilling_phases")
    op.drop_column("afes", "reopened_by")
    op.drop_column("afes", "reopened_at")
    op.drop_column("afes", "reopen_remarks")
    op.drop_column("afes", "depth_unit_id")
    op.drop_column("afes", "total_planned_depth")
    op.drop_column("afes", "total_planned_days")
    op.drop_column("afes", "budget_amount")
