# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Idempotent DDL helpers for Alembic migrations.

Deployments that were created before the clean ``20260827_0001`` baseline (or
that had their schema built by hand / by ``Base.metadata.create_all``) can end
up with tables that already exist while ``alembic_version`` still points at an
earlier revision. Re-running ``alembic upgrade head`` there aborts with
``psycopg.errors.DuplicateTable: relation "..." already exists`` and leaves the
deployment stuck: the migration cannot move forward and there is nothing to
roll back.

The helpers below make ``CREATE TABLE`` / ``CREATE INDEX`` steps skip objects
that are already present, so a partially provisioned database converges on the
expected schema instead of failing. They inspect the live connection rather
than relying on ``IF NOT EXISTS`` so the behaviour is identical across
backends and so callers can log what was skipped.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# Default width used when a string column does not advertise a length (TEXT).
_DEFAULT_STRING_LENGTH = 50


def string_column_max_length(column_type: Any, default: int = _DEFAULT_STRING_LENGTH) -> int:
    """Return the VARCHAR length of ``column_type``, or ``default`` when unbounded."""

    length = getattr(column_type, "length", None)
    if isinstance(length, int) and length > 0:
        return length
    return default


def unique_placeholder_code(
    row_id: object,
    existing_codes: set[str],
    max_length: int,
    prefix: str = "",
) -> str:
    """Return a unique placeholder that always fits in ``max_length`` characters.

    Concatenating a prefix with a UUID primary key (``C{uuid}``) overflows
    short columns such as ``currencies.currency_code VARCHAR(10)`` and aborts
    PostgreSQL with ``StringDataRightTruncation``. Integer ids that already
    fit (``C1``, ``TMP5``) are kept as-is so existing backfills stay stable.
    """

    if max_length < 1:
        max_length = 1

    naive = f"{prefix}{row_id}"
    if naive and len(naive) <= max_length and naive not in existing_codes:
        return naive

    seed = str(row_id)
    for nonce in range(10_000):
        digest = hashlib.sha1(f"{seed}:{nonce}".encode()).hexdigest()
        if prefix and max_length > 1:
            candidate = (prefix[0] + digest)[:max_length]
        else:
            candidate = digest[:max_length]
        if candidate not in existing_codes:
            return candidate

    return uuid.uuid4().hex[:max_length]


def backfill_unique_string_column(
    table_name: str,
    column_name: str,
    *,
    schema: str | None = None,
    max_length: int | None = None,
) -> None:
    """Fill NULL/empty values of a unique string column with length-safe codes.

    Used both when a missing ``*_code`` column is added onto a legacy table
    and by the dedicated master-data backfill revision. Legacy deployments
    may use UUID primary keys, so placeholders are sized to the live column.
    """

    inspector = _inspector()
    if not inspector.has_table(table_name, schema=schema):
        return
    columns = {column["name"]: column for column in inspector.get_columns(table_name, schema=schema)}
    if column_name not in columns or "id" not in columns:
        return
    if max_length is None:
        max_length = string_column_max_length(columns[column_name]["type"])

    bind = op.get_bind()
    existing_codes: set[str] = set()
    try:
        result = bind.execute(
            sa.text(
                f"SELECT {column_name} FROM {table_name} "
                f"WHERE {column_name} IS NOT NULL AND {column_name} != ''"
            )
        )
        existing_codes = {str(row[0]) for row in result if row[0] is not None}
    except Exception:
        existing_codes = set()

    try:
        result = bind.execute(
            sa.text(f"SELECT id FROM {table_name} WHERE {column_name} IS NULL OR {column_name} = ''")
        )
        rows = result.fetchall()
    except Exception:
        rows = []

    prefix = "C" if table_name == "currencies" else "TMP"
    for (row_id,) in rows:
        candidate = unique_placeholder_code(row_id, existing_codes, max_length, prefix=prefix)
        bind.execute(
            sa.text(f"UPDATE {table_name} SET {column_name} = :code WHERE id = :id"),
            {"code": candidate, "id": row_id},
        )
        existing_codes.add(candidate)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def table_exists(table_name: str, *, schema: str | None = None) -> bool:
    """Return ``True`` when ``table_name`` is already present in the database."""

    return _inspector().has_table(table_name, schema=schema)


def index_exists(table_name: str, index_name: str, *, schema: str | None = None) -> bool:
    """Return ``True`` when ``index_name`` already exists on ``table_name``."""

    inspector = _inspector()
    if not inspector.has_table(table_name, schema=schema):
        return False
    names = {index["name"] for index in inspector.get_indexes(table_name, schema=schema)}
    # A unique index backing a UNIQUE constraint is reported separately on some
    # backends, so consider those names taken as well.
    names.update(
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name, schema=schema)
    )
    return index_name in names


def _add_column(table_name: str, column: sa.Column, schema: str | None) -> None:
    """Add a single column, falling back when the backend rejects the default.

    SQLite cannot ``ALTER TABLE ... ADD COLUMN`` with a non-constant default
    such as ``now()``. The attempt runs inside a savepoint so a rejection can be
    recovered from on backends (PostgreSQL) that otherwise abort the whole
    migration transaction; the fallback adds a plain nullable column and
    backfills it with the intended default.
    """

    bind = op.get_bind()
    server_default = column.server_default
    try:
        with bind.begin_nested():
            if schema:
                op.add_column(table_name, column, schema=schema)
            else:
                op.add_column(table_name, column)
        return
    except sa.exc.DatabaseError:
        if server_default is None:
            raise
        logger.warning(
            "Could not add %r.%r with its server default; adding it nullable and backfilling.",
            table_name,
            column.name,
        )

    fallback = sa.Column(column.name, column.type, nullable=True)
    if schema:
        op.add_column(table_name, fallback, schema=schema)
    else:
        op.add_column(table_name, fallback)

    default_arg = getattr(server_default, "arg", None)
    if default_arg is not None:
        qualified = f"{schema}.{table_name}" if schema else table_name
        target = sa.table(table_name, sa.column(column.name), schema=schema)
        if isinstance(default_arg, sa.sql.ClauseElement):
            expression: Any = default_arg
        else:
            expression = sa.literal(default_arg)
        op.execute(
            target.update()
            .where(sa.column(column.name).is_(None))
            .values(**{column.name: expression})
        )
        logger.info("Backfilled %r.%r with its default value.", qualified, column.name)


def add_missing_columns(table_name: str, *columns: Any, schema: str | None = None) -> None:
    """Add any of ``columns`` that the existing ``table_name`` does not have.

    Used to reconcile a pre-existing table with the definition a migration
    expects. A column declared ``NOT NULL`` without a server default cannot be
    added to a table that may already hold rows, so it is added as nullable and
    the discrepancy is logged rather than raising.
    """

    inspector = _inspector()
    existing = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for column in columns:
        if not isinstance(column, sa.Column) or column.name in existing:
            continue
        forced_nullable = False
        if not column.nullable and column.server_default is None:
            logger.warning(
                "Column %r.%r is missing and NOT NULL without a default; adding it as nullable.",
                table_name,
                column.name,
            )
            column.nullable = True
            forced_nullable = True
        _add_column(table_name, column, schema)
        if forced_nullable and isinstance(column.type, (sa.String, sa.Text)):
            is_code_column = column.name.endswith("_code")
            insp_cols = {c["name"] for c in _inspector().get_columns(table_name, schema=schema)}
            if is_code_column and "id" in insp_cols:
                backfill_unique_string_column(
                    table_name,
                    column.name,
                    schema=schema,
                    max_length=string_column_max_length(column.type),
                )
                logger.info("Backfilled %r.%r with unique placeholders.", table_name, column.name)
            else:
                target = sa.table(table_name, sa.column(column.name), schema=schema)
                op.execute(
                    target.update()
                    .where(sa.column(column.name).is_(None))
                    .values(**{column.name: ""})
                )
                logger.info("Backfilled %r.%r with an empty string.", table_name, column.name)


def create_table_if_missing(table_name: str, *columns: Any, **kwargs: Any) -> None:
    """``op.create_table`` that is a no-op when the table already exists.

    When the table is already there its columns are reconciled with the
    definition so a database provisioned by an older schema still gains the
    columns this revision introduces.
    """

    schema = kwargs.get("schema")
    if table_exists(table_name, schema=schema):
        logger.info("Table %r already exists; skipping creation.", table_name)
        add_missing_columns(table_name, *columns, schema=schema)
        return
    op.create_table(table_name, *columns, **kwargs)


def create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    **kwargs: Any,
) -> None:
    """``op.create_index`` that is a no-op when the index already exists."""

    if index_exists(table_name, index_name, schema=kwargs.get("schema")):
        logger.info("Index %r on %r already exists; skipping creation.", index_name, table_name)
        return
    op.create_index(index_name, table_name, columns, **kwargs)


def drop_table_if_present(table_name: str, *, schema: str | None = None) -> None:
    """``op.drop_table`` that tolerates an already-absent table."""

    if not table_exists(table_name, schema=schema):
        logger.info("Table %r is absent; skipping drop.", table_name)
        return
    op.drop_table(table_name, schema=schema) if schema else op.drop_table(table_name)


def drop_index_if_present(index_name: str, table_name: str, *, schema: str | None = None) -> None:
    """``op.drop_index`` that tolerates an already-absent index."""

    if not index_exists(table_name, index_name, schema=schema):
        logger.info("Index %r on %r is absent; skipping drop.", index_name, table_name)
        return
    if schema:
        op.drop_index(index_name, table_name=table_name, schema=schema)
    else:
        op.drop_index(index_name, table_name=table_name)
