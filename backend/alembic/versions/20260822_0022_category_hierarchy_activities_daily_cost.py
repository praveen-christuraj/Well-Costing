"""Category hierarchy, activities, well sub-activities, daily cost activity tracking

* primary_categories — user-configurable top-level classification (replaces
  hardcoded applies_to values on item_categories).
* secondary_categories — second-level classification linked to a primary
  category (replaces item_subcategories conceptually).
* tertiary_categories — third-level classification linked to a secondary
  category; auto-links to primary through secondary.
* cost_categories gains secondary_category_id (parent from secondary).
* catalog_items gains tertiary_category_id.
* activities — master-data table for Planned, NPT, UPA.
* well_activities — well-scoped sub-activities linked to a primary activity.
* daily_cost_entries gains sub_activity_id for activity-based cost tracking.
* daily_cost_service_lines gains sub_activity_id and override_rate.

Revision ID: 20260822_0022
Revises: 20260822_0021
Create Date: 2026-08-22 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0022"
down_revision: str | None = "20260822_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts_cols() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    ]


def upgrade() -> None:
    # --- primary_categories ---------------------------------------------------
    op.create_table(
        "primary_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_primary_categories_code"),
    )
    op.create_index("ix_primary_categories_code", "primary_categories", ["code"])
    op.create_index("ix_primary_categories_name", "primary_categories", ["name"])
    op.create_index("ix_primary_categories_is_active", "primary_categories", ["is_active"])

    # --- secondary_categories -------------------------------------------------
    op.create_table(
        "secondary_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("primary_category_id", sa.Uuid(), nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_secondary_categories_code"),
        sa.ForeignKeyConstraint(
            ["primary_category_id"],
            ["primary_categories.id"],
            ondelete="RESTRICT",
            name="fk_secondary_categories_primary_category_id_primary_categories",
        ),
    )
    op.create_index("ix_secondary_categories_code", "secondary_categories", ["code"])
    op.create_index("ix_secondary_categories_name", "secondary_categories", ["name"])
    op.create_index(
        "ix_secondary_categories_primary_category_id",
        "secondary_categories",
        ["primary_category_id"],
    )
    op.create_index(
        "ix_secondary_categories_is_active", "secondary_categories", ["is_active"]
    )

    # --- tertiary_categories --------------------------------------------------
    op.create_table(
        "tertiary_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("secondary_category_id", sa.Uuid(), nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_tertiary_categories_code"),
        sa.ForeignKeyConstraint(
            ["secondary_category_id"],
            ["secondary_categories.id"],
            ondelete="RESTRICT",
            # PostgreSQL identifiers are limited to 63 characters; the default
            # convention-derived name is 65 chars, so use an explicit short name.
            name="fk_tertiary_categories_secondary_category_id",
        ),
    )
    op.create_index("ix_tertiary_categories_code", "tertiary_categories", ["code"])
    op.create_index("ix_tertiary_categories_name", "tertiary_categories", ["name"])
    op.create_index(
        "ix_tertiary_categories_secondary_category_id",
        "tertiary_categories",
        ["secondary_category_id"],
    )
    op.create_index("ix_tertiary_categories_is_active", "tertiary_categories", ["is_active"])

    # --- cost_categories: add secondary_category_id ---------------------------
    op.add_column(
        "cost_categories",
        sa.Column("secondary_category_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cost_categories_secondary_category_id_secondary_categories",
        "cost_categories",
        "secondary_categories",
        ["secondary_category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_cost_categories_secondary_category_id",
        "cost_categories",
        ["secondary_category_id"],
    )

    # --- catalog_items: add tertiary_category_id ------------------------------
    op.add_column(
        "catalog_items",
        sa.Column("tertiary_category_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_catalog_items_tertiary_category_id_tertiary_categories",
        "catalog_items",
        "tertiary_categories",
        ["tertiary_category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_catalog_items_tertiary_category_id",
        "catalog_items",
        ["tertiary_category_id"],
    )

    # --- activities (master data: Planned, NPT, UPA) -------------------------
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_activities_code"),
    )
    op.create_index("ix_activities_code", "activities", ["code"])
    op.create_index("ix_activities_name", "activities", ["name"])
    op.create_index("ix_activities_is_active", "activities", ["is_active"])

    # --- well_activities (well-scoped sub-activities) ------------------------
    op.create_table(
        "well_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("well_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("responsible_party", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["well_id"], ["wells.id"], ondelete="CASCADE", name="fk_well_activities_well_id_wells"
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            ondelete="RESTRICT",
            name="fk_well_activities_activity_id_activities",
        ),
        sa.UniqueConstraint(
            "well_id", "name", name="uq_well_activities_well_name"
        ),
    )
    op.create_index("ix_well_activities_well_id", "well_activities", ["well_id"])
    op.create_index("ix_well_activities_activity_id", "well_activities", ["activity_id"])
    op.create_index("ix_well_activities_is_active", "well_activities", ["is_active"])

    # --- daily_cost_entries: add sub_activity tracking -----------------------
    # Remove the unique constraint on (well_id, entry_date) so we can have
    # multiple entries per well per date (one per sub-activity).
    # Note: SQLite does not support DROP CONSTRAINT, so we handle this
    # conditionally.
    # NOTE: column must be added BEFORE creating a constraint that references it.
    op.add_column(
        "daily_cost_entries",
        sa.Column("sub_activity_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_cost_entries_sub_activity_id_well_activities",
        "daily_cost_entries",
        "well_activities",
        ["sub_activity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_daily_cost_entries_sub_activity_id",
        "daily_cost_entries",
        ["sub_activity_id"],
    )

    dialect = op.get_bind().dialect.name
    if dialect != "sqlite":
        op.drop_constraint(
            "uq_daily_cost_entries_well_date", "daily_cost_entries", type_="unique"
        )
        op.create_unique_constraint(
            "uq_daily_cost_entries_well_date_activity",
            "daily_cost_entries",
            ["well_id", "entry_date", "sub_activity_id"],
        )

    # --- daily_cost_service_lines: add sub_activity_id, override_rate --------
    op.add_column(
        "daily_cost_service_lines",
        sa.Column("sub_activity_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_cost_service_lines_sub_activity_id_well_activities",
        "daily_cost_service_lines",
        "well_activities",
        ["sub_activity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_daily_cost_service_lines_sub_activity_id",
        "daily_cost_service_lines",
        ["sub_activity_id"],
    )
    op.add_column(
        "daily_cost_service_lines",
        sa.Column("override_rate", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "daily_cost_service_lines",
        sa.Column("service_type", sa.String(30), server_default="operation", nullable=False),
    )

    # --- daily_cost_consumable_lines: add sub_activity_id, override_rate -----
    op.add_column(
        "daily_cost_consumable_lines",
        sa.Column("sub_activity_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_cost_consumable_lines_sub_activity_id_well_activities",
        "daily_cost_consumable_lines",
        "well_activities",
        ["sub_activity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_daily_cost_consumable_lines_sub_activity_id",
        "daily_cost_consumable_lines",
        ["sub_activity_id"],
    )
    op.add_column(
        "daily_cost_consumable_lines",
        sa.Column("override_rate", sa.Numeric(18, 4), nullable=True),
    )

    # --- Seed default activities -----------------------------------------------
    op.execute(
        "INSERT INTO activities (id, code, name, description, sequence, is_active, created_at, updated_at) "
        "VALUES "
        "(gen_random_uuid(), 'PLANNED', 'Planned', 'Planned operational activities', 1, true, now(), now()), "
        "(gen_random_uuid(), 'NPT', 'NPT', 'Non Productive Time', 2, true, now(), now()), "
        "(gen_random_uuid(), 'UPA', 'UPA', 'Unplanned Activity', 3, true, now(), now())"
    )


def downgrade() -> None:
    op.drop_column("daily_cost_consumable_lines", "override_rate")
    op.drop_index("ix_daily_cost_consumable_lines_sub_activity_id", "daily_cost_consumable_lines")
    op.drop_constraint(
        "fk_daily_cost_consumable_lines_sub_activity_id_well_activities",
        "daily_cost_consumable_lines",
        type_="foreignkey",
    )
    op.drop_column("daily_cost_consumable_lines", "sub_activity_id")

    op.drop_column("daily_cost_service_lines", "service_type")
    op.drop_column("daily_cost_service_lines", "override_rate")
    op.drop_index("ix_daily_cost_service_lines_sub_activity_id", "daily_cost_service_lines")
    op.drop_constraint(
        "fk_daily_cost_service_lines_sub_activity_id_well_activities",
        "daily_cost_service_lines",
        type_="foreignkey",
    )
    op.drop_column("daily_cost_service_lines", "sub_activity_id")

    # Reverse the unique-constraint swap before dropping the column it depends on.
    dialect = op.get_bind().dialect.name
    if dialect != "sqlite":
        op.drop_constraint(
            "uq_daily_cost_entries_well_date_activity",
            "daily_cost_entries",
            type_="unique",
        )
        op.create_unique_constraint(
            "uq_daily_cost_entries_well_date",
            "daily_cost_entries",
            ["well_id", "entry_date"],
        )

    op.drop_index("ix_daily_cost_entries_sub_activity_id", "daily_cost_entries")
    op.drop_constraint(
        "fk_daily_cost_entries_sub_activity_id_well_activities",
        "daily_cost_entries",
        type_="foreignkey",
    )
    op.drop_column("daily_cost_entries", "sub_activity_id")

    op.drop_table("well_activities")
    op.drop_table("activities")

    op.drop_index("ix_catalog_items_tertiary_category_id", "catalog_items")
    op.drop_constraint(
        "fk_catalog_items_tertiary_category_id_tertiary_categories", "catalog_items"
    )
    op.drop_column("catalog_items", "tertiary_category_id")

    op.drop_index("ix_cost_categories_secondary_category_id", "cost_categories")
    op.drop_constraint(
        "fk_cost_categories_secondary_category_id_secondary_categories", "cost_categories"
    )
    op.drop_column("cost_categories", "secondary_category_id")

    op.drop_table("tertiary_categories")
    op.drop_table("secondary_categories")
    op.drop_table("primary_categories")
