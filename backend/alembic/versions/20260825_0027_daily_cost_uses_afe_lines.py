"""Link Daily Cost lines directly to configured AFE lines.

The current AFE stores the user-selected classification directly and no longer
requires a catalogue item. Daily Cost therefore keeps the AFE line as its
primary planning reference; catalogue item references remain nullable for
historical records.

Revision ID: 20260825_0027
Revises: 20260825_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0027"
down_revision: str | None = "20260825_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    for table in ("daily_cost_service_lines", "daily_cost_consumable_lines"):
        op.add_column(table, sa.Column("afe_line_id", sa.Uuid(), nullable=True))
        op.create_index(f"ix_{table}_afe_line_id", table, ["afe_line_id"])
        if not sqlite:
            op.create_foreign_key(
                f"fk_{table}_afe_line_id_afe_lines",
                table,
                "afe_lines",
                ["afe_line_id"],
                ["id"],
                ondelete="RESTRICT",
            )

    with op.batch_alter_table("daily_cost_service_lines") as batch:
        batch.alter_column("service_id", existing_type=sa.Uuid(), nullable=True)
    with op.batch_alter_table("daily_cost_consumable_lines") as batch:
        batch.alter_column("consumable_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("daily_cost_service_lines") as batch:
        batch.alter_column("service_id", existing_type=sa.Uuid(), nullable=False)
    with op.batch_alter_table("daily_cost_consumable_lines") as batch:
        batch.alter_column("consumable_id", existing_type=sa.Uuid(), nullable=False)

    sqlite = op.get_bind().dialect.name == "sqlite"
    for table in ("daily_cost_service_lines", "daily_cost_consumable_lines"):
        if not sqlite:
            op.drop_constraint(f"fk_{table}_afe_line_id_afe_lines", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_afe_line_id", table_name=table)
        op.drop_column(table, "afe_line_id")
