"""Add service types and rate-category pricing to AFE workflow.

Revision ID: 20260825_0028
Revises: 20260825_0027
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0028"
down_revision = "20260825_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("afe_lines", sa.Column("service_type", sa.String(length=20), nullable=False, server_default="service"))
    op.create_check_constraint("valid_afe_line_service_type", "afe_lines", "service_type IN ('service','tangible','consumable','other')")
    # AFE lines define scope and costing behaviour, not a planned purchase quantity/UOM.
    op.alter_column("afe_lines", "quantity", nullable=True)
    op.alter_column("afe_lines", "unit_id", nullable=True)

    for name in (
        "operating_rate", "standby_rate", "mobilization_rate", "demobilization_rate",
        "fixed_charges", "personnel_operating_rate", "personnel_standby_rate", "other_rate",
    ):
        op.add_column("afe_cost_estimate_lines", sa.Column(name, sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("afe_cost_estimate_lines", sa.Column("multiply_by_input", sa.Boolean(), nullable=False, server_default=sa.true()))
    # Keep legacy unit_rate as operating-rate compatibility for existing integrations.


def downgrade() -> None:
    op.drop_column("afe_cost_estimate_lines", "multiply_by_input")
    for name in (
        "other_rate", "personnel_standby_rate", "personnel_operating_rate", "fixed_charges",
        "demobilization_rate", "mobilization_rate", "standby_rate", "operating_rate",
    ):
        op.drop_column("afe_cost_estimate_lines", name)
    op.drop_constraint("valid_afe_line_service_type", "afe_lines", type_="check")
    op.drop_column("afe_lines", "service_type")
