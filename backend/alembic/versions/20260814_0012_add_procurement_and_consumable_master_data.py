"""add procurement and consumable master data

Adds vendor classification, catalogue item categories, mud chemicals, cement
additives, service orders, purchase orders, column-based service rate cards, and
effective-dated item prices.

Revision ID: 20260814_0012
Revises: 20260813_0011
Create Date: 2026-08-14 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0012"
down_revision: str | None = "20260813_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VALID_ITEM_TYPES = (
    "item_type IN ('service','tangible','material','equipment',"
    "'mud_chemical','cement_additive')"
)
OLD_ITEM_TYPES = "item_type IN ('service','tangible','material','equipment')"

_NEW_ITEM_TYPE_CHECK = (
    "CONSTRAINT valid_item_type CHECK (item_type IN ('service','tangible',"
    "'material','equipment','mud_chemical','cement_additive'))"
)
_LEGACY_ITEM_TYPE_CHECK = (
    "CONSTRAINT ck_catalog_items_valid_item_type CHECK "
    "(item_type IN ('service','tangible','material','equipment'))"
)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _sqlite_rebuild_catalog_items_constraints(bind) -> None:
    """Replace the restrictive item-type CHECK on catalog_items on SQLite.

    SQLite cannot ALTER or DROP a CHECK constraint, so the table is rebuilt in
    the standard rename-copy dance. ``PRAGMA legacy_alter_table=ON`` keeps
    every other table's FOREIGN KEY clause pointing at the original table name
    (the default OFF behaviour would retarget them onto the scratch table),
    and all indexes are reflected and recreated on the rebuilt table.
    """
    import re

    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes("catalog_items")
    columns = [column["name"] for column in inspector.get_columns("catalog_items")]
    create_sql = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": "catalog_items"},
    ).scalar_one()

    pattern = re.compile(
        r"CONSTRAINT ck_catalog_items_valid_item_type CHECK \(item_type IN \([^)]*\)\)"
    )
    rebuilt_sql, replacements = pattern.subn(_NEW_ITEM_TYPE_CHECK, create_sql)
    if replacements != 1:
        raise RuntimeError(
            "Could not locate the catalog_items item-type CHECK constraint to replace"
        )
    rebuilt_sql = (
        rebuilt_sql.rstrip()[:-1]
        + ", CONSTRAINT fk_catalog_items_item_category_id_item_categories"
        + " FOREIGN KEY(item_category_id) REFERENCES item_categories(id))"
    )

    temporary = "_swap_catalog_items"
    previous_legacy = bind.exec_driver_sql("PRAGMA legacy_alter_table").scalar()
    bind.exec_driver_sql("PRAGMA legacy_alter_table=ON")
    bind.exec_driver_sql(f'ALTER TABLE "catalog_items" RENAME TO "{temporary}"')
    bind.exec_driver_sql(rebuilt_sql)
    column_list = ", ".join(f'"{column}"' for column in columns)
    bind.exec_driver_sql(
        f'INSERT INTO "catalog_items" ({column_list}) SELECT {column_list} FROM "{temporary}"'
    )
    bind.exec_driver_sql(f'DROP TABLE "{temporary}"')
    bind.exec_driver_sql("PRAGMA legacy_alter_table=" + ("ON" if previous_legacy else "OFF"))
    for index in indexes:
        op.create_index(
            index["name"],
            "catalog_items",
            list(index["column_names"]),
            unique=bool(index["unique"]),
        )


def _sqlite_rebuild_catalog_items_legacy(bind) -> None:
    """Reverse the upgrade's catalog_items rebuild on SQLite.

    SQLite can neither drop a column that appears in a foreign-key clause nor
    replace a CHECK constraint, so the extension columns
    (``item_category_id``, ``material_number``, ``specification``,
    ``manufacturer``), the item-category foreign key, and the widened
    item-type CHECK are removed by rebuilding the table with the original
    narrow, originally named CHECK. ``PRAGMA legacy_alter_table=ON`` keeps
    referencing foreign keys pointing at ``catalog_items`` throughout.
    """
    import re

    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes("catalog_items")
    create_sql = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": "catalog_items"},
    ).scalar_one()

    create_sql = re.sub(
        r"CONSTRAINT valid_item_type CHECK \(item_type IN \([^)]*\)\)",
        _LEGACY_ITEM_TYPE_CHECK,
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    # Drop the item-category FK clause whether it is the last constraint in
    # the table or sits between other constraints.
    fk_clause = (
        r"CONSTRAINT fk_catalog_items_item_category_id_item_categories\s+"
        r"FOREIGN KEY\s*\(\s*\"?item_category_id\"?\s*\)\s*REFERENCES\s*"
        r"\"?item_categories\"?\s*\(\s*\"?id\"?\s*\)"
    )
    create_sql = re.sub(
        r",\s*" + fk_clause + r"\s*(?=\))", "", create_sql, count=1, flags=re.IGNORECASE
    )
    create_sql = re.sub(fk_clause + r"\s*,", "", create_sql, count=1, flags=re.IGNORECASE)
    for column in ("item_category_id", "material_number", "specification", "manufacturer"):
        create_sql = re.sub(
            r'^[ \t]*"?' + column + r'"?[^,\n]*,[ \t]*$\n',
            "",
            create_sql,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )

    columns = [
        column["name"]
        for column in inspector.get_columns("catalog_items")
        if column["name"]
        not in {"item_category_id", "material_number", "specification", "manufacturer"}
    ]
    temporary = "_swap_catalog_items_legacy"
    previous_legacy = bind.exec_driver_sql("PRAGMA legacy_alter_table").scalar()
    bind.exec_driver_sql("PRAGMA legacy_alter_table=ON")
    bind.exec_driver_sql(f'ALTER TABLE "catalog_items" RENAME TO "{temporary}"')
    bind.exec_driver_sql(create_sql)
    column_list = ", ".join(f'"{column}"' for column in columns)
    bind.exec_driver_sql(
        f'INSERT INTO "catalog_items" ({column_list}) SELECT {column_list} FROM "{temporary}"'
    )
    bind.exec_driver_sql(f'DROP TABLE "{temporary}"')
    bind.exec_driver_sql("PRAGMA legacy_alter_table=" + ("ON" if previous_legacy else "OFF"))
    for index in indexes:
        op.create_index(
            index["name"],
            "catalog_items",
            list(index["column_names"]),
            unique=bool(index["unique"]),
        )


def _audit_columns() -> list[sa.Column]:
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
    # --- vendor classification -------------------------------------------------
    op.add_column(
        "vendors",
        sa.Column(
            "vendor_type",
            sa.String(length=20),
            server_default="third_party",
            nullable=False,
        ),
    )
    op.add_column("vendors", sa.Column("contact_person", sa.String(length=150), nullable=True))
    op.add_column("vendors", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("vendors", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("vendors", sa.Column("country", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_vendors_vendor_type"), "vendors", ["vendor_type"])
    if not _is_sqlite():  # SQLite cannot add constraints to existing tables
        op.create_check_constraint(
            "valid_vendor_type", "vendors", "vendor_type IN ('third_party','inhouse')"
        )

    # --- item categories -------------------------------------------------------
    op.create_table(
        "item_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("applies_to", sa.String(length=30), server_default="tangible", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "applies_to IN ('service','tangible','mud_chemical','cement_additive')",
            name=op.f("ck_item_categories_valid_item_category_scope"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_categories")),
    )
    op.create_index(op.f("ix_item_categories_code"), "item_categories", ["code"], unique=True)
    op.create_index(op.f("ix_item_categories_name"), "item_categories", ["name"])
    op.create_index(op.f("ix_item_categories_is_active"), "item_categories", ["is_active"])
    op.create_index(op.f("ix_item_categories_applies_to"), "item_categories", ["applies_to"])

    # --- catalogue item extensions --------------------------------------------
    op.add_column("catalog_items", sa.Column("item_category_id", sa.Uuid(), nullable=True))
    op.add_column(
        "catalog_items", sa.Column("material_number", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "catalog_items", sa.Column("specification", sa.String(length=255), nullable=True)
    )
    op.add_column("catalog_items", sa.Column("manufacturer", sa.String(length=150), nullable=True))
    op.create_index(
        op.f("ix_catalog_items_item_category_id"), "catalog_items", ["item_category_id"]
    )
    op.create_index(
        op.f("ix_catalog_items_material_number"), "catalog_items", ["material_number"]
    )
    if _is_sqlite():
        # SQLite cannot ALTER constraints, so the old item-type CHECK (which
        # would reject mud_chemical/cement_additive rows) is swapped out by
        # rebuilding the table; the item-category FK is added in the same DDL.
        _sqlite_rebuild_catalog_items_constraints(op.get_bind())
    else:
        op.create_foreign_key(
            op.f("fk_catalog_items_item_category_id_item_categories"),
            "catalog_items",
            "item_categories",
            ["item_category_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.drop_constraint(
            op.f("ck_catalog_items_valid_item_type"), "catalog_items", type_="check"
        )
        op.create_check_constraint("valid_item_type", "catalog_items", VALID_ITEM_TYPES)

    # --- consumable subtype tables --------------------------------------------
    for table in ("mud_chemicals", "cement_additives"):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(
                ["id"],
                ["catalog_items.id"],
                name=op.f(f"fk_{table}_id_catalog_items"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        )

    # --- service orders --------------------------------------------------------
    op.create_table(
        "service_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("currency_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("contract_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name=op.f("ck_service_orders_valid_service_order_range"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','expired','cancelled')",
            name=op.f("ck_service_orders_valid_service_order_status"),
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_service_orders_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_service_orders_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_orders")),
    )
    op.create_index(
        op.f("ix_service_orders_order_number"), "service_orders", ["order_number"], unique=True
    )
    op.create_index(op.f("ix_service_orders_title"), "service_orders", ["title"])
    op.create_index(op.f("ix_service_orders_vendor_id"), "service_orders", ["vendor_id"])
    op.create_index(op.f("ix_service_orders_currency_id"), "service_orders", ["currency_id"])
    op.create_index(op.f("ix_service_orders_valid_from"), "service_orders", ["valid_from"])
    op.create_index(op.f("ix_service_orders_valid_to"), "service_orders", ["valid_to"])
    op.create_index(op.f("ix_service_orders_status"), "service_orders", ["status"])
    op.create_index(op.f("ix_service_orders_is_active"), "service_orders", ["is_active"])

    # --- purchase orders -------------------------------------------------------
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("currency_id", sa.Uuid(), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("order_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("status", sa.String(length=25), server_default="draft", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('draft','open','partially_received','closed','cancelled')",
            name=op.f("ck_purchase_orders_valid_purchase_order_status"),
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_purchase_orders_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_purchase_orders_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
    )
    op.create_index(
        op.f("ix_purchase_orders_order_number"), "purchase_orders", ["order_number"], unique=True
    )
    op.create_index(op.f("ix_purchase_orders_title"), "purchase_orders", ["title"])
    op.create_index(op.f("ix_purchase_orders_vendor_id"), "purchase_orders", ["vendor_id"])
    op.create_index(op.f("ix_purchase_orders_currency_id"), "purchase_orders", ["currency_id"])
    op.create_index(op.f("ix_purchase_orders_order_date"), "purchase_orders", ["order_date"])
    op.create_index(op.f("ix_purchase_orders_status"), "purchase_orders", ["status"])
    op.create_index(op.f("ix_purchase_orders_is_active"), "purchase_orders", ["is_active"])

    # --- service rate cards ----------------------------------------------------
    op.create_table(
        "service_rate_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("service_order_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("hole_section", sa.String(length=60), nullable=True),
        sa.Column(
            "operating_rate", sa.Numeric(precision=18, scale=4), server_default="0", nullable=False
        ),
        sa.Column(
            "standby_rate", sa.Numeric(precision=18, scale=4), server_default="0", nullable=False
        ),
        sa.Column(
            "mobilisation_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "demobilisation_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_service_rate_cards_valid_service_rate_range"),
        ),
        sa.CheckConstraint(
            "operating_rate >= 0 AND standby_rate >= 0 "
            "AND mobilisation_rate >= 0 AND demobilisation_rate >= 0",
            name=op.f("ck_service_rate_cards_non_negative_service_rates"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["catalog_items.id"],
            name=op.f("fk_service_rate_cards_service_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_service_rate_cards_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_order_id"],
            ["service_orders.id"],
            name=op.f("fk_service_rate_cards_service_order_id_service_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_service_rate_cards_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_service_rate_cards_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_rate_cards")),
    )
    for column in (
        "service_id",
        "vendor_id",
        "service_order_id",
        "currency_id",
        "unit_id",
        "hole_section",
        "effective_from",
        "effective_to",
        "is_active",
    ):
        op.create_index(
            op.f(f"ix_service_rate_cards_{column}"), "service_rate_cards", [column]
        )

    # --- item prices -----------------------------------------------------------
    op.create_table(
        "item_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "unit_price >= 0", name=op.f("ck_item_prices_non_negative_unit_price")
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_item_prices_valid_item_price_range"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["catalog_items.id"],
            name=op.f("fk_item_prices_item_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_item_prices_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_item_prices_purchase_order_id_purchase_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_item_prices_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_item_prices_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_prices")),
    )
    for column in (
        "item_id",
        "vendor_id",
        "purchase_order_id",
        "currency_id",
        "unit_id",
        "effective_from",
        "effective_to",
        "is_active",
    ):
        op.create_index(op.f(f"ix_item_prices_{column}"), "item_prices", [column])


def downgrade() -> None:
    op.drop_table("item_prices")
    op.drop_table("service_rate_cards")
    op.drop_table("purchase_orders")
    op.drop_table("service_orders")
    op.drop_table("cement_additives")
    op.drop_table("mud_chemicals")

    op.drop_index(op.f("ix_catalog_items_material_number"), table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_item_category_id"), table_name="catalog_items")
    if _is_sqlite():
        # SQLite cannot drop a column that appears in a foreign-key clause or
        # replace CHECK constraints, so the extension columns and the
        # item-category FK are removed and the original item-type CHECK
        # restored by rebuilding the table.
        _sqlite_rebuild_catalog_items_legacy(op.get_bind())
    else:
        # The upgrade replaced ck_catalog_items_valid_item_type with
        # valid_item_type, so the downgrade restores them the same way.
        op.drop_constraint("valid_item_type", "catalog_items", type_="check")
        op.create_check_constraint(
            op.f("ck_catalog_items_valid_item_type"), "catalog_items", OLD_ITEM_TYPES
        )
        op.drop_constraint(
            op.f("fk_catalog_items_item_category_id_item_categories"),
            "catalog_items",
            type_="foreignkey",
        )
        op.drop_column("catalog_items", "manufacturer")
        op.drop_column("catalog_items", "specification")
        op.drop_column("catalog_items", "material_number")
        op.drop_column("catalog_items", "item_category_id")

    op.drop_table("item_categories")

    if not _is_sqlite():  # constraint was never created on SQLite
        op.drop_constraint(op.f("ck_vendors_valid_vendor_type"), "vendors", type_="check")
    op.drop_index(op.f("ix_vendors_vendor_type"), table_name="vendors")
    op.drop_column("vendors", "country")
    op.drop_column("vendors", "phone")
    op.drop_column("vendors", "email")
    op.drop_column("vendors", "contact_person")
    op.drop_column("vendors", "vendor_type")
