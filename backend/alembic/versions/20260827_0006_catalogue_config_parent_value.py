"""Add parent_value to catalogue_configs for dependent dropdowns.

Revision ID: 20260827_0006
Revises: 20260827_0005
Create Date: 2026-08-27

Tangible subcategories are dependents of tangible categories: each
``tangible_subcategory`` value carries the category it belongs to in
``parent_value``. Other config types (bit types, manufacturers, categories)
keep ``parent_value`` NULL.

The unique constraint changes from (config_type, value) to
(config_type, parent_value, value) so the same subcategory name may exist
under different categories. Rows with a NULL parent (legacy values created
before this change, and all non-parented config types) stay unique per type
through the application-level duplicate checks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.migration_ops import add_missing_columns, create_index_if_missing, index_exists

revision: str = "20260827_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Replay-safe guard: the column only ever appears together with the new
    # constraint pair, so an already-migrated table (e.g. a re-run after the
    # alembic_version marker was reset) is left untouched.
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("catalogue_configs")
    }
    if "parent_value" in existing_columns:
        return

    add_missing_columns(
        "catalogue_configs",
        sa.Column("parent_value", sa.String(length=200), nullable=True),
    )
    # Recreate the uniqueness constraint with the parent dimension. Batch
    # mode keeps this portable across PostgreSQL (direct ALTER) and SQLite
    # (table rebuild).
    with op.batch_alter_table("catalogue_configs") as batch_op:
        batch_op.drop_constraint(op.f("uq_catalogue_configs_type_value"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_catalogue_configs_type_parent_value"),
            ["config_type", "parent_value", "value"],
        )
    create_index_if_missing(
        op.f("ix_catalogue_configs_type_parent"),
        "catalogue_configs",
        ["config_type", "parent_value"],
    )


def downgrade() -> None:
    # A parented subcategory can clash with another parent's same-named row
    # once the parent dimension disappears; keep only the lowest-id row per
    # (config_type, value) pair so the old unique constraint can be restored.
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            """
            SELECT c.id FROM catalogue_configs c
            WHERE EXISTS (
                SELECT 1 FROM catalogue_configs older
                WHERE older.config_type = c.config_type
                  AND older.value = c.value
                  AND older.id < c.id
            )
            """
        )
    ).fetchall()
    for (record_id,) in duplicates:
        conn.execute(sa.text("DELETE FROM catalogue_configs WHERE id = :id"), {"id": record_id})

    # Drop the parent-aware index first: SQLite batch mode recreates every
    # reflected index, and it cannot recreate this one after parent_value is
    # removed in the same batch.
    if index_exists("catalogue_configs", op.f("ix_catalogue_configs_type_parent")):
        op.drop_index(op.f("ix_catalogue_configs_type_parent"), table_name="catalogue_configs")

    with op.batch_alter_table("catalogue_configs") as batch_op:
        batch_op.drop_constraint(op.f("uq_catalogue_configs_type_parent_value"), type_="unique")
        batch_op.create_unique_constraint(
            op.f("uq_catalogue_configs_type_value"),
            ["config_type", "value"],
        )
        batch_op.drop_column("parent_value")
