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

Reconciling stops being possible when the existing table's primary key has a
different type from the declared one - a ``mud_chemicals`` left behind by an
older schema is keyed by UUID while the models declare integers. PostgreSQL
then rejects every foreign key referencing it with ``DatatypeMismatch`` and the
ORM cannot map its rows either. ``create_table_if_missing`` takes an
``incompatible_pk_suffix`` for exactly that case: the old table is renamed
aside with its rows and the declared table is created in its place. Foreign
keys pointing at tables a revision does not own are skipped with a warning
when their key types do not match.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Sequence
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


def type_family(column_type: Any, dialect: Any = None) -> str:
    """The dialect's base type name for ``column_type``, e.g. ``VARCHAR``.

    Lengths and precisions are stripped (``VARCHAR(50)`` -> ``VARCHAR``,
    ``NUMERIC(18, 2)`` -> ``NUMERIC``) because a foreign key or primary key only
    requires both sides to share a base type. Comparing the compiled names lets
    a declared ``sa.String`` match a reflected ``VARCHAR`` and a declared
    ``sa.Integer`` disagree with a reflected ``UUID``.
    """

    if dialect is None:
        dialect = op.get_bind().dialect
    try:
        compiled = str(column_type.compile(dialect=dialect))
    except Exception:  # pragma: no cover - defensive for exotic types
        return type(column_type).__name__.upper()
    return compiled.split("(")[0].strip().upper()


def live_type_family(
    table_name: str,
    column_name: str,
    *,
    schema: str | None = None,
    dialect: Any = None,
) -> str | None:
    """Type family of ``column_name`` as it exists in the database right now.

    ``None`` means the table or the column is not there (yet), so callers cannot
    draw any conclusion.
    """

    inspector = _inspector()
    if not inspector.has_table(table_name, schema=schema):
        return None
    for column in inspector.get_columns(table_name, schema=schema):
        if column["name"] == column_name:
            return type_family(column["type"], dialect)
    return None


def _constraint_column_names(constraint: Any) -> list[str]:
    """Column names a not-yet-attached ``PrimaryKeyConstraint``/FK declares."""

    attached = [getattr(column, "name", None) for column in getattr(constraint, "columns", [])]
    if attached and all(attached):
        return [name for name in attached if name]
    pending = getattr(constraint, "_pending_colargs", None) or []
    return [
        name
        for name in (
            column.name if isinstance(column, sa.Column) else str(column) for column in pending
        )
        if name
    ]


def _foreign_key_target(element: Any) -> str | None:
    """``"table.column"`` a ``ForeignKey`` element points at, attached or not."""

    colspec = getattr(element, "_colspec", None)
    if isinstance(colspec, str):
        return colspec
    try:
        target = element.column
    except Exception:  # unattached ForeignKey objects raise on access
        return None
    table = getattr(target, "table", None)
    if table is not None and getattr(target, "name", None):
        return f"{table.name}.{target.name}"
    return None


def _split_fk_target(target: str) -> tuple[str | None, str, str]:
    """``"schema.table.column"`` (schema optional) into its three parts."""

    parts = target.split(".")
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    return None, "", parts[0]


def _probe_column(column: sa.Column) -> sa.Column:
    """A detached stand-in for ``column`` good enough to resolve constraints.

    ``Column.copy()`` is deprecated and ``Column._copy()`` is private, so the
    probe carries only what primary-key and foreign-key resolution reads.
    """

    return sa.Column(column.name, column.type, primary_key=column.primary_key, nullable=column.nullable)


def _probe_table(table_name: str, columns: Sequence[Any], kwargs: dict[str, Any]) -> Any | None:
    """A throwaway ``Table`` resolving string-named columns and constraints.

    ``create_table_if_missing`` receives constraints declared with plain column
    names (``sa.ForeignKeyConstraint(["chemical_id"], ["mud_chemicals.id"])``),
    which only resolve once attached to a table. Attaching the *caller's*
    objects would make the real ``op.create_table`` fail with
    ``Column object 'id' already assigned to Table``, so the probe is built from
    copies, with stub tables standing in for the foreign-key targets. ``None``
    means the definition could not be resolved, and callers must then assume
    everything is compatible.
    """

    probe_args: list[Any] = []
    fk_targets: list[tuple[str | None, str, str]] = []
    for arg in columns:
        if isinstance(arg, sa.Column):
            probe_args.append(_probe_column(arg))
        elif isinstance(arg, sa.ForeignKeyConstraint):
            targets = [target for target in (_foreign_key_target(e) for e in arg.elements) if target]
            local = _constraint_column_names(arg)
            if not local or len(local) != len(targets):
                return None
            fk_targets.extend(_split_fk_target(target) for target in targets)
            probe_args.append(
                sa.ForeignKeyConstraint(local, targets, name=arg.name, ondelete=arg.ondelete)
            )
        elif isinstance(arg, (sa.PrimaryKeyConstraint, sa.UniqueConstraint)):
            names = _constraint_column_names(arg)
            if not names:
                return None
            kind = (
                sa.PrimaryKeyConstraint
                if isinstance(arg, sa.PrimaryKeyConstraint)
                else sa.UniqueConstraint
            )
            probe_args.append(kind(*names, name=arg.name))
        elif isinstance(arg, sa.Constraint):
            return None
        else:
            probe_args.append(arg)

    schema = kwargs.get("schema")
    metadata = sa.MetaData()
    stubs: dict[tuple[str | None, str], set[str]] = {}
    for target_schema, target_table, target_column in fk_targets:
        if not target_table:
            return None
        if target_schema == schema and target_table == table_name:
            continue  # self-referential: the probe table already has the column
        stubs.setdefault((target_schema, target_table), set()).add(target_column)
    for (target_schema, target_table), target_columns in stubs.items():
        sa.Table(
            target_table,
            metadata,
            *(sa.Column(name, sa.types.NullType()) for name in sorted(target_columns)),
            schema=target_schema,
        )

    try:
        return sa.Table(table_name, metadata, *probe_args, schema=schema)
    except Exception:  # pragma: no cover - defensive for unusual definitions
        return None


def declared_primary_key_families(
    table_name: str,
    columns: Sequence[Any],
    kwargs: dict[str, Any],
    dialect: Any = None,
) -> list[str]:
    """Type families of the primary key a ``create_table`` call declares."""

    table = _probe_table(table_name, columns, kwargs)
    if table is None:
        return []
    return [type_family(column.type, dialect) for column in table.primary_key.columns]


def live_primary_key_families(
    table_name: str,
    *,
    schema: str | None = None,
    dialect: Any = None,
) -> list[str] | None:
    """Type families of the primary key the existing table actually has."""

    inspector = _inspector()
    if not inspector.has_table(table_name, schema=schema):
        return None
    pk_columns = inspector.get_pk_constraint(table_name, schema=schema).get("constrained_columns")
    if not pk_columns:
        return []
    families: list[str] = []
    for column in inspector.get_columns(table_name, schema=schema):
        if column["name"] in pk_columns:
            families.append(type_family(column["type"], dialect))
    return families


def primary_key_is_compatible(
    table_name: str,
    columns: Sequence[Any],
    kwargs: dict[str, Any],
    *,
    schema: str | None = None,
    dialect: Any = None,
) -> bool:
    """Whether the live table's primary key can back the declared one.

    A table left behind by an older schema often uses UUID primary keys while
    the application models declare integer ones. Such a table cannot host the
    child tables' foreign keys (PostgreSQL refuses with ``DatatypeMismatch``)
    and the ORM cannot map its rows either, so callers rename it aside and
    create the table this revision actually defines.
    """

    declared = declared_primary_key_families(table_name, columns, kwargs, dialect)
    live = live_primary_key_families(table_name, schema=schema, dialect=dialect)
    if not declared or live is None:
        return True
    if len(declared) != len(live):
        return False
    return declared == live


def _rename_indexes(table_name: str, suffix: str, *, schema: str | None = None) -> None:
    """Rename a quarantined table's indexes so the new table can reuse the names.

    PostgreSQL index names are shared by the whole schema, so the index backing
    ``pk_mud_chemicals`` on the quarantined copy would otherwise make the new
    table's own primary key fail with ``relation "pk_mud_chemicals" already
    exists``. Renaming a constraint renames its index; plain indexes are renamed
    directly. SQLite has no equivalent statement, so it is skipped there.
    """

    if op.get_bind().dialect.name != "postgresql":
        return

    inspector = _inspector()
    qualified = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    constraints = [
        name
        for name in (
            inspector.get_pk_constraint(table_name, schema=schema).get("name"),
            *(
                constraint.get("name")
                for constraint in inspector.get_unique_constraints(table_name, schema=schema)
            ),
        )
        if name
    ]
    for name in constraints:
        op.execute(
            sa.text(
                f'ALTER TABLE {qualified} '
                f'RENAME CONSTRAINT "{name}" TO "{_suffixed(name, suffix)}"'
            )
        )

    index_names = {index["name"] for index in inspector.get_indexes(table_name, schema=schema)}
    for name in sorted(index_names - set(constraints)):
        op.execute(sa.text(f'ALTER INDEX "{name}" RENAME TO "{_suffixed(name, suffix)}"'))


def _suffixed(name: str, suffix: str, limit: int = 63) -> str:
    """``name`` with ``suffix`` appended, truncated to the identifier limit."""

    candidate = f"{name}_{suffix}"
    if len(candidate) <= limit:
        return candidate
    return f"{name[: max(1, limit - len(suffix) - 1)]}_{suffix}"[:limit]


def quarantine_table(table_name: str, *, suffix: str, schema: str | None = None) -> str:
    """Rename ``table_name`` aside and return the name it moved to.

    Used when an existing table cannot host the schema this revision defines
    (incompatible primary key). The rows are kept under the new name instead of
    being dropped so an operator can migrate or inspect them by hand.
    """

    inspector = _inspector()
    existing = set(inspector.get_table_names(schema=schema))
    target = _suffixed(table_name, suffix)
    counter = 2
    while target in existing:
        target = _suffixed(f"{table_name}_{counter}", suffix)
        counter += 1

    _rename_indexes(table_name, suffix, schema=schema)
    if schema:
        op.rename_table(table_name, target, schema=schema)
    else:
        op.rename_table(table_name, target)
    logger.warning(
        "Table %r already exists with an incompatible primary key; renamed it to "
        "%r and created the table this revision defines. Review the renamed rows "
        "and drop or migrate them once you are done.",
        table_name,
        target,
    )
    return target


def drop_incompatible_foreign_keys(
    table_name: str,
    columns: Sequence[Any],
    kwargs: dict[str, Any],
    *,
    schema: str | None = None,
    dialect: Any = None,
) -> list[Any]:
    """``columns`` without foreign keys the live database cannot honour.

    When the referenced table already exists with a primary key of a different
    type (a legacy UUID-keyed ``vendor_suppliers``, say) PostgreSQL rejects the
    whole ``CREATE TABLE`` with ``DatatypeMismatch``. Skipping just that
    constraint lets the migration finish; the missing link is logged loudly
    because the referenced table is not the one the application expects.
    """

    table = _probe_table(table_name, columns, kwargs)
    if table is None:
        return list(columns)

    unusable: set[str] = set()
    for foreign_key in table.foreign_keys:
        referred = foreign_key.column
        live = live_type_family(
            referred.table.name,
            referred.name,
            schema=referred.table.schema,
            dialect=dialect,
        )
        if live is None:
            continue  # referenced table is created later in this migration
        if live != type_family(foreign_key.parent.type, dialect):
            unusable.add(foreign_key.parent.name)
            logger.warning(
                "Skipping %r: %s.%s is %s in this database but %r declares %s; the "
                "referenced table does not match the schema the application expects.",
                getattr(foreign_key.constraint, "name", None) or f"fk_{foreign_key.parent.name}",
                referred.table.name,
                referred.name,
                live,
                table_name,
                type_family(foreign_key.parent.type, dialect),
            )

    if not unusable:
        return list(columns)

    kept: list[Any] = []
    for arg in columns:
        if isinstance(arg, sa.ForeignKeyConstraint) and set(_constraint_column_names(arg)) & unusable:
            continue
        kept.append(arg)
    return kept


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


def create_table_if_missing(
    table_name: str,
    *columns: Any,
    incompatible_pk_suffix: str | None = None,
    **kwargs: Any,
) -> None:
    """``op.create_table`` that is a no-op when the table already exists.

    When the table is already there its columns are reconciled with the
    definition so a database provisioned by an older schema still gains the
    columns this revision introduces.

    Reconciling is impossible when the existing table's primary key has a
    different type from the declared one (legacy tables keyed by UUID, for
    instance): the ORM cannot map its rows and PostgreSQL rejects every child
    foreign key pointing at it. Pass ``incompatible_pk_suffix`` to have such a
    table renamed to ``<table>_<suffix>`` - rows included - and replaced by the
    table this revision defines.
    """

    schema = kwargs.get("schema")
    if table_exists(table_name, schema=schema):
        if primary_key_is_compatible(table_name, columns, kwargs, schema=schema):
            logger.info("Table %r already exists; skipping creation.", table_name)
            add_missing_columns(table_name, *columns, schema=schema)
            return
        if not incompatible_pk_suffix:
            logger.warning(
                "Table %r already exists with primary key %s while this revision "
                "declares %s; keeping the existing table.",
                table_name,
                live_primary_key_families(table_name, schema=schema),
                declared_primary_key_families(table_name, columns, kwargs),
            )
            add_missing_columns(table_name, *columns, schema=schema)
            return
        quarantine_table(table_name, suffix=incompatible_pk_suffix, schema=schema)
    op.create_table(table_name, *drop_incompatible_foreign_keys(table_name, columns, kwargs), **kwargs)


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
