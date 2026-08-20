"""service rate basis and configurable item sub categories

* services gain ``rate_basis`` (daily / per_service / per_section / fixed) so
  the catalogue can classify how each service is charged before it is priced
  per well,
* a new configurable ``item_subcategories`` table gives tangibles (and any
  other catalogue scope) a user-defined second-level classification, and
  ``catalog_items.sub_category_id`` links catalogue items to it.

Revision ID: 20260820_0016
Revises: 20260820_0015
Create Date: 2026-08-20 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0016"
down_revision: str | None = "20260820_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ITEM_SCOPE_CHECK = "applies_to IN ('service','tangible','mud_chemical','cement_additive')"
RATE_BASIS_CHECK = "rate_basis IN ('daily','per_service','per_section','fixed')"


def upgrade() -> None:
    # --- services: pricing-model classification ------------------------------
    op.add_column(
        "services",
        sa.Column("rate_basis", sa.String(20), server_default="daily", nullable=False),
    )
    op.create_check_constraint(
        "valid_service_rate_basis", "services", RATE_BASIS_CHECK
    )
    op.create_index(op.f("ix_services_rate_basis"), "services", ["rate_basis"])

    # --- configurable item sub categories -------------------------------------
    op.create_table(
        "item_subcategories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "applies_to", sa.String(30), server_default="tangible", nullable=False
        ),
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
        sa.CheckConstraint(
            ITEM_SCOPE_CHECK, name=op.f("ck_item_subcategories_valid_item_subcategory_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_subcategories")),
        sa.UniqueConstraint("code", name=op.f("uq_item_subcategories_code")),
    )
    op.create_index(
        op.f("ix_item_subcategories_code"), "item_subcategories", ["code"], unique=True
    )
    op.create_index(op.f("ix_item_subcategories_name"), "item_subcategories", ["name"])
    op.create_index(
        op.f("ix_item_subcategories_is_active"), "item_subcategories", ["is_active"]
    )
    op.create_index(
        op.f("ix_item_subcategories_applies_to"), "item_subcategories", ["applies_to"]
    )

    # --- catalogue items link to a sub category --------------------------------
    with op.batch_alter_table("catalog_items") as batch:
        batch.add_column(sa.Column("sub_category_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_catalog_items_sub_category_id_item_subcategories"),
            "item_subcategories",
            ["sub_category_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        op.f("ix_catalog_items_sub_category_id"), "catalog_items", ["sub_category_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_catalog_items_sub_category_id"), table_name="catalog_items")
    with op.batch_alter_table("catalog_items") as batch:
        batch.drop_constraint(
            op.f("fk_catalog_items_sub_category_id_item_subcategories"),
            type_="foreignkey",
        )
        batch.drop_column("sub_category_id")

    op.drop_index(op.f("ix_item_subcategories_applies_to"), table_name="item_subcategories")
    op.drop_index(op.f("ix_item_subcategories_is_active"), table_name="item_subcategories")
    op.drop_index(op.f("ix_item_subcategories_name"), table_name="item_subcategories")
    op.drop_index(op.f("ix_item_subcategories_code"), table_name="item_subcategories")
    op.drop_table("item_subcategories")

    op.drop_index(op.f("ix_services_rate_basis"), table_name="services")
    op.drop_constraint("valid_service_rate_basis", "services", type_="check")
    op.drop_column("services", "rate_basis")
