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

import logging
from typing import Any

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")


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
        if not column.nullable and column.server_default is None:
            logger.warning(
                "Column %r.%r is missing and NOT NULL without a default; adding it as nullable.",
                table_name,
                column.name,
            )
            column.nullable = True
        _add_column(table_name, column, schema)


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
