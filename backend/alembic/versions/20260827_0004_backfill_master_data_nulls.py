"""Backfill NULL values on master-data string columns left nullable by legacy tables.

Revision ID: 20260827_0004
Revises: 20260827_0003
Create Date: 2026-08-27

When a pre-existing ``currencies`` / ``activities`` / ``hole_sections`` table
was reconciled by ``20260827_0002``, required string columns such as
``currency_symbol`` were added as nullable (they cannot be added ``NOT NULL``
without a default onto a table that already has rows). Listing those records
then failed Pydantic validation and the API returned a generic 500.

This revision fills remaining NULLs so the pages load. Unique ``*_code``
placeholders are sized to the live column: concatenating ``C`` with a UUID
primary key overflowed ``currencies.currency_code VARCHAR(10)`` on PostgreSQL
(``StringDataRightTruncation``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.migration_ops import backfill_unique_string_column

revision: str = "20260827_0004"
down_revision: str | None = "20260827_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILLS: tuple[tuple[str, str, str | None], ...] = (
    ("uom", "unit_symbol", "unit_code"),
    ("uom", "unit_name", "unit_code"),
    ("uom", "unit_code", None),
    ("currencies", "currency_symbol", "currency_code"),
    ("currencies", "currency_name", "currency_code"),
    ("currencies", "currency_code", None),
    ("phases", "phase_name", "phase_code"),
    ("phases", "phase_code", None),
    ("activities", "activity_name", "activity_code"),
    ("activities", "activity_code", None),
    ("hole_sections", "section_name", "section_code"),
    ("hole_sections", "section_code", None),
    ("vendor_suppliers", "vendor_name", "vendor_code"),
    ("vendor_suppliers", "vendor_code", None),
)


def _table_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _backfill_string(table_name: str, column_name: str, fallback_column: str | None) -> None:
    columns = _table_columns(table_name)
    if column_name not in columns:
        return

    if fallback_column and fallback_column in columns:
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET {column_name} = {fallback_column} "
                f"WHERE {column_name} IS NULL AND {fallback_column} IS NOT NULL AND {fallback_column} != ''"
            )
        )

    if fallback_column is None:
        # This is a unique ``*_code`` column. Setting multiple NULLs to '' violates
        # the unique index (ix_*_code). Generate a unique placeholder per row
        # that fits the live VARCHAR length (UUID ids must not be concatenated
        # raw into currency_code VARCHAR(10)).
        if "id" not in columns:
            # No id to key off - fall back to random short strings
            try:
                op.execute(
                    sa.text(
                        f"UPDATE {table_name} SET {column_name} = substr(md5(random()::text),1,8) "
                        f"WHERE {column_name} IS NULL OR {column_name} = ''"
                    )
                )
            except Exception:
                # SQLite fallback
                op.execute(
                    sa.text(
                        f"UPDATE {table_name} SET {column_name} = substr(hex(randomblob(4)),1,8) "
                        f"WHERE {column_name} IS NULL OR {column_name} = ''"
                    )
                )
            return

        backfill_unique_string_column(table_name, column_name)
    else:
        op.execute(sa.text(f"UPDATE {table_name} SET {column_name} = '' WHERE {column_name} IS NULL"))


def _backfill_flag(table_name: str, column_name: str) -> None:
    columns = _table_columns(table_name)
    if column_name not in columns:
        return
    table = sa.table(table_name, sa.column(column_name))
    op.execute(table.update().where(sa.column(column_name).is_(None)).values(**{column_name: False}))


def upgrade() -> None:
    for table_name, column_name, fallback in _BACKFILLS:
        _backfill_string(table_name, column_name, fallback)

    for table_name in (
        "uom",
        "currencies",
        "phases",
        "activities",
        "hole_sections",
        "vendor_suppliers",
        "purchase_orders_service_orders",
    ):
        _backfill_flag(table_name, "is_deleted")


def downgrade() -> None:
    # Data backfill is not reversed.
    return
