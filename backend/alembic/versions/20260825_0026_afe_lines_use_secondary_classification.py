"""Use the secondary classification as the AFE line dependency.

New AFE lines no longer require a catalogue item. Existing lines retain their
catalogue reference for audit/history and are backfilled from that item's
secondary classification.

Revision ID: 20260825_0026
Revises: 20260824_0025
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0026"
down_revision: str | None = "20260824_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("afe_lines", sa.Column("secondary_category_id", sa.Uuid(), nullable=True))
    op.create_index("ix_afe_lines_secondary_category_id", "afe_lines", ["secondary_category_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_afe_lines_secondary_category_id_secondary_categories",
            "afe_lines", "secondary_categories", ["secondary_category_id"], ["id"], ondelete="RESTRICT",
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text("""
            UPDATE afe_lines SET secondary_category_id = (
                SELECT secondary_category_id FROM catalog_items
                WHERE catalog_items.id = afe_lines.catalog_item_id
            )
        """))
    else:
        op.execute(sa.text("""
            UPDATE afe_lines SET secondary_category_id = catalog_items.secondary_category_id
            FROM catalog_items WHERE catalog_items.id = afe_lines.catalog_item_id
        """))
    # Legacy data without a secondary classification must be classified before
    # it can be edited. Keep the migration deployable while new API writes make
    # the field mandatory.
    with op.batch_alter_table("afe_lines") as batch:
        batch.alter_column("catalog_item_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("afe_lines") as batch:
        batch.alter_column("catalog_item_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_afe_lines_secondary_category_id", table_name="afe_lines")
    op.drop_column("afe_lines", "secondary_category_id")
