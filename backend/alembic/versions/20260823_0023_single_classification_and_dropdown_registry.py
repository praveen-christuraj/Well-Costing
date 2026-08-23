"""Single classification for catalogue items and cost categories; dropdown registry

Item categories and item sub categories are retired: the Primary → Secondary →
Tertiary hierarchy introduced in 20260822_0022 is now the only classification in
the application.

* ``catalog_items`` gains ``primary_category_id`` and ``secondary_category_id``
  (it already had ``tertiary_category_id``) and loses ``item_category_id`` and
  ``sub_category_id``.
* ``cost_categories`` gains ``primary_category_id`` — the parent of a cost
  category is now a primary category rather than another cost category.
* Existing ``item_categories`` rows are converted into secondary categories under
  a primary category per catalogue scope, and the sub categories actually in use
  become tertiary categories under the matching secondary, so no classification
  that a user typed in is lost.
* ``item_categories`` and ``item_subcategories`` are dropped.
* ``dropdown_bindings`` is created: the super-admin overrides of which registered
  source feeds which dropdown slot.

Revision ID: 20260823_0023
Revises: 20260822_0022
Create Date: 2026-08-23 09:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0023"
down_revision: str | None = "20260822_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Catalogue scope → (primary category code, primary category name).
SCOPE_PRIMARIES: dict[str, tuple[str, str]] = {
    "service": ("SERVICES", "Services"),
    "tangible": ("TANGIBLES", "Tangibles"),
    "mud_chemical": ("MUD-CHEMICALS", "Mud Chemicals"),
    "cement_additive": ("CEMENT-ADDITIVES", "Cement Additives"),
    "material": ("MATERIALS", "Materials"),
    "equipment": ("EQUIPMENT", "Equipment"),
}


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


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


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def _add_fk_column(table: str, column: str, target: str) -> None:
    """Add a nullable UUID FK column, skipping the FK itself on SQLite."""

    if _has_column(table, column):
        return
    if _is_sqlite():
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
    else:
        op.add_column(
            table,
            sa.Column(
                column,
                sa.Uuid(),
                sa.ForeignKey(f"{target}.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )
    op.create_index(f"ix_{table}_{column}", table, [column])


def _unique_code(conn: sa.Connection, table: str, base: str) -> str:
    """A code not yet used in ``table`` — codes are unique per level."""

    candidate = (base or "CATEGORY").strip().upper()[:100]
    suffix = 1
    while conn.execute(
        sa.text(f"SELECT 1 FROM {table} WHERE code = :code"), {"code": candidate}
    ).first():
        suffix += 1
        candidate = f"{base.strip().upper()[:94]}-{suffix}"
    return candidate


def _now() -> datetime:
    return datetime.now(UTC)


def _insert_category(
    conn: sa.Connection,
    table: str,
    *,
    code: str,
    name: str,
    description: str | None,
    parent_column: str | None = None,
    parent_id: str | None = None,
) -> str:
    new_id = str(uuid4())
    params: dict[str, object] = {
        "id": new_id,
        "code": code,
        "name": name,
        "description": description,
        "is_active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if parent_column:
        params[parent_column] = parent_id
    columns_sql = ", ".join(params)
    values_sql = ", ".join(f":{column}" for column in params)
    conn.execute(
        sa.text(f"INSERT INTO {table} ({columns_sql}) VALUES ({values_sql})"),
        params,
    )
    return new_id


def _ensure_primary(conn: sa.Connection, cache: dict[str, str], scope: str) -> str:
    """The primary category standing for one catalogue scope, created on demand."""

    if scope in cache:
        return cache[scope]
    code, name = SCOPE_PRIMARIES.get(scope, (scope.upper(), scope.replace("_", " ").title()))
    row = conn.execute(
        sa.text("SELECT id FROM primary_categories WHERE code = :code"), {"code": code}
    ).first()
    if row is not None:
        cache[scope] = str(row[0])
        return cache[scope]
    cache[scope] = _insert_category(
        conn,
        "primary_categories",
        code=code,
        name=name,
        description="Created automatically when item categories moved into the classification.",
    )
    return cache[scope]


def _migrate_item_categories() -> None:
    """Convert item categories/sub categories into the classification hierarchy."""

    conn = op.get_bind()
    if not _has_table("item_categories"):
        return

    primaries: dict[str, str] = {}
    secondary_for_item_category: dict[str, str] = {}

    for row in conn.execute(
        sa.text("SELECT id, code, name, description, applies_to FROM item_categories")
    ).mappings():
        primary_id = _ensure_primary(conn, primaries, str(row["applies_to"] or "tangible"))
        secondary_for_item_category[str(row["id"])] = _insert_category(
            conn,
            "secondary_categories",
            code=_unique_code(conn, "secondary_categories", str(row["code"])),
            name=str(row["name"]),
            description=row["description"],
            parent_column="primary_category_id",
            parent_id=primary_id,
        )

    # Sub categories only become tertiary categories where an item actually uses
    # them, because a tertiary category must sit under a known secondary parent.
    tertiary_for_pair: dict[tuple[str, str], str] = {}
    sub_categories = {
        str(row["id"]): row
        for row in conn.execute(
            sa.text("SELECT id, code, name, description FROM item_subcategories")
        ).mappings()
    }

    items = conn.execute(
        sa.text(
            "SELECT id, item_type, item_category_id, sub_category_id, tertiary_category_id "
            "FROM catalog_items"
        )
    ).mappings()
    for item in items:
        secondary_id = secondary_for_item_category.get(str(item["item_category_id"] or ""))
        tertiary_id = str(item["tertiary_category_id"]) if item["tertiary_category_id"] else None

        sub_id = str(item["sub_category_id"] or "")
        if secondary_id and sub_id in sub_categories and tertiary_id is None:
            key = (secondary_id, sub_id)
            if key not in tertiary_for_pair:
                sub = sub_categories[sub_id]
                tertiary_for_pair[key] = _insert_category(
                    conn,
                    "tertiary_categories",
                    code=_unique_code(conn, "tertiary_categories", str(sub["code"])),
                    name=str(sub["name"]),
                    description=sub["description"],
                    parent_column="secondary_category_id",
                    parent_id=secondary_id,
                )
            tertiary_id = tertiary_for_pair[key]

        primary_id = None
        if secondary_id:
            parent = conn.execute(
                sa.text("SELECT primary_category_id FROM secondary_categories WHERE id = :id"),
                {"id": secondary_id},
            ).first()
            primary_id = str(parent[0]) if parent else None
        elif item["item_type"]:
            primary_id = _ensure_primary(conn, primaries, str(item["item_type"]))

        conn.execute(
            sa.text(
                "UPDATE catalog_items SET primary_category_id = :primary, "
                "secondary_category_id = :secondary, tertiary_category_id = :tertiary "
                "WHERE id = :id"
            ),
            {
                "primary": primary_id,
                "secondary": secondary_id,
                "tertiary": tertiary_id,
                "id": str(item["id"]),
            },
        )


def _backfill_cost_categories() -> None:
    """A cost category's parent becomes the primary of its secondary category."""

    op.get_bind().execute(
        sa.text(
            "UPDATE cost_categories SET primary_category_id = ("
            "  SELECT s.primary_category_id FROM secondary_categories s"
            "  WHERE s.id = cost_categories.secondary_category_id"
            ") WHERE secondary_category_id IS NOT NULL"
        )
    )


def upgrade() -> None:
    # --- new classification columns ------------------------------------------
    _add_fk_column("catalog_items", "primary_category_id", "primary_categories")
    _add_fk_column("catalog_items", "secondary_category_id", "secondary_categories")
    _add_fk_column("cost_categories", "primary_category_id", "primary_categories")

    # --- carry the existing classification across -----------------------------
    _migrate_item_categories()
    _backfill_cost_categories()

    # --- retire item categories ----------------------------------------------
    # SQLite cannot drop a column that a table-level foreign key still mentions,
    # so the table is rebuilt in batch mode there; PostgreSQL drops the
    # constraint and the column directly.
    retired = [
        column
        for column in ("item_category_id", "sub_category_id")
        if _has_column("catalog_items", column)
    ]
    for column in retired:
        op.drop_index(f"ix_catalog_items_{column}", table_name="catalog_items")
    if retired and _is_sqlite():
        with op.batch_alter_table("catalog_items", recreate="always") as batch:
            for column in retired:
                batch.drop_column(column)
    else:
        for column, referenced in (
            ("item_category_id", "item_categories"),
            ("sub_category_id", "item_subcategories"),
        ):
            if column not in retired:
                continue
            op.drop_constraint(
                f"fk_catalog_items_{column}_{referenced}", "catalog_items", type_="foreignkey"
            )
            op.drop_column("catalog_items", column)
    if _has_table("item_subcategories"):
        op.drop_table("item_subcategories")
    if _has_table("item_categories"):
        op.drop_table("item_categories")

    # --- dropdown registry ----------------------------------------------------
    op.create_table(
        "dropdown_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slot_code", sa.String(120), nullable=False),
        sa.Column("source_code", sa.String(120), nullable=False),
        sa.Column("filters", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("label_template", sa.String(120), nullable=True),
        sa.Column("sort_by", sa.String(60), nullable=True),
        sa.Column("include_inactive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_code", name="uq_dropdown_bindings_slot_code"),
    )
    op.create_index("ix_dropdown_bindings_slot_code", "dropdown_bindings", ["slot_code"])
    op.create_index("ix_dropdown_bindings_source_code", "dropdown_bindings", ["source_code"])
    op.create_index("ix_dropdown_bindings_is_active", "dropdown_bindings", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_dropdown_bindings_is_active", table_name="dropdown_bindings")
    op.drop_index("ix_dropdown_bindings_source_code", table_name="dropdown_bindings")
    op.drop_index("ix_dropdown_bindings_slot_code", table_name="dropdown_bindings")
    op.drop_table("dropdown_bindings")

    op.create_table(
        "item_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("applies_to", sa.String(30), server_default="tangible", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_item_categories_code"),
    )
    op.create_table(
        "item_subcategories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("applies_to", sa.String(30), server_default="tangible", nullable=False),
        *_ts_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_item_subcategories_code"),
    )
    for table in ("item_categories", "item_subcategories"):
        op.create_index(f"ix_{table}_code", table, ["code"], unique=True)
        op.create_index(f"ix_{table}_name", table, ["name"])
        op.create_index(f"ix_{table}_is_active", table, ["is_active"])
        op.create_index(f"ix_{table}_applies_to", table, ["applies_to"])

    # Restore the columns *with* their foreign keys so the earlier migrations,
    # which drop those constraints by name, can still run.
    with op.batch_alter_table("catalog_items") as batch:
        batch.add_column(sa.Column("item_category_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("sub_category_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("catalog_items") as batch:
        batch.create_foreign_key(
            "fk_catalog_items_item_category_id_item_categories",
            "item_categories",
            ["item_category_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_catalog_items_sub_category_id_item_subcategories",
            "item_subcategories",
            ["sub_category_id"],
            ["id"],
        )
    op.create_index("ix_catalog_items_item_category_id", "catalog_items", ["item_category_id"])
    op.create_index("ix_catalog_items_sub_category_id", "catalog_items", ["sub_category_id"])

    op.drop_index("ix_cost_categories_primary_category_id", table_name="cost_categories")
    op.drop_column("cost_categories", "primary_category_id")
    op.drop_index("ix_catalog_items_secondary_category_id", table_name="catalog_items")
    op.drop_column("catalog_items", "secondary_category_id")
    op.drop_index("ix_catalog_items_primary_category_id", table_name="catalog_items")
    op.drop_column("catalog_items", "primary_category_id")
