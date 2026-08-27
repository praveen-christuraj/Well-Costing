# TEMPORARY ONE-OFF MAINTENANCE SCRIPT — delete it once the databases have been cleaned.
"""Clean out the tables left over from before the restructure and rebuild only the current ones.

The live databases predate the module restructure: the schema still carries tables for AFE,
AFE Cost Estimates, Daily Cost, Well Activities, Cost Control, Cost Builder, Reports and
Assurance, while the migration history was reset to the single baseline ``20260827_0001``.
``alembic upgrade head`` cannot reconcile that state (the 28 old revisions are gone) and
``downgrade base`` has nothing to roll back — which is why ``docs/database/overview.md``
prescribes *drop and recreate*. This script automates that prescription:

1. Inspect the live schema and classify every table/view: *stale* — nothing in the code
   refers to it any more; *current* — a model in ``app/models`` owns it. The models are
   the single source of truth; no table list is hard-coded here.
2. Report the plan, including how many rows each table would lose.
3. Optionally export every table that is about to be dropped to CSV plus DDL.
4. Drop the stale objects. Then, when the current tables cannot be reconciled (missing
   tables/columns, or an ``alembic_version`` the migration chain no longer recognises),
   drop those too along with ``alembic_version``.
5. Rebuild with ``alembic upgrade head`` rather than ``Base.metadata.create_all``, so the
   recreated tables come from the migrations and ``alembic_version`` ends up stamped at
   head instead of silently lying about the database.
6. Verify the result with the application's own drift detector.

Re-running the script on an already-clean database is therefore a no-op instead of a second
wipe; pass ``--rebuild`` to force the full drop-and-recreate, or ``--prune-only`` to drop
nothing but the stale objects.

Safety rails: dry run unless ``--execute`` is passed, ``--confirm CLEAN`` required to
execute, and hosted environments refused unless ``--allow-hosted`` is given. No credentials
live in this file; the database URL comes from the same settings the backend uses, so run it
from ``backend/`` where ``.env`` sits.

Usage::

    cd backend
    python scripts/temp_clean_database.py                          # report only (default)
    python scripts/temp_clean_database.py --backup-dir /tmp/db-backup
    python scripts/temp_clean_database.py --execute --confirm CLEAN
    python scripts/temp_clean_database.py --execute --confirm CLEAN --rebuild
    python scripts/temp_clean_database.py --execute --confirm CLEAN --prune-only

"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running as `python scripts/temp_clean_database.py` from any directory: Python
# only puts the script's own folder (backend/scripts) on sys.path, so point at the
# backend root to make `app` importable without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import Settings, get_settings
from app.db.alembic_url import escape_for_alembic
from app.db.base import Base
from app.db.schema import (
    ALEMBIC_INI,
    ALEMBIC_SCRIPTS,
    current_revision,
    detect_schema_drift,
    expected_head_revision,
)
from sqlalchemy import MetaData, Table, bindparam, create_engine, inspect, text
from sqlalchemy.engine import Connection, Dialect, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

CONFIRM_PHRASE = "CLEAN"
HOSTED_ENVIRONMENTS = frozenset({"uat", "staging", "production"})
DROP_VERBS = {"TABLE": "DROP TABLE", "VIEW": "DROP VIEW", "MATERIALIZED VIEW": "DROP MATERIALIZED VIEW"}

# Bookkeeping table owned by Alembic rather than by the application.
ALEMBIC_VERSION_TABLE = "alembic_version"
PROTECTED_TABLES = frozenset({ALEMBIC_VERSION_TABLE})
# Objects belonging to other tooling (providers, ORMs, PostGIS) that may share the schema.
# Never dropped, so cleaning cannot damage a managed project's plumbing.
FOREIGN_TABLES = frozenset(
    {
        "_prisma_migrations",
        "django_migrations",
        "flyway_schema_history",
        "geometry_columns",
        "geography_columns",
        "schema_migrations",
        "spatial_ref_sys",
    }
)

# What the code currently believes the schema should contain.
EXPECTED_TABLES: frozenset[str] = frozenset(Base.metadata.tables)


@dataclass(frozen=True)
class DbObject:
    """One relation in the live database, annotated with the row count used for reporting."""

    name: str
    kind: str  # TABLE | VIEW | MATERIALIZED VIEW
    schema: str | None
    rows: int | None = None

    @property
    def qualified(self) -> str:
        return _qualify(self.schema, self.name)

    def drop_statement(self, dialect: Dialect) -> str:
        cascade = " CASCADE" if dialect.name == "postgresql" else ""
        return f"{DROP_VERBS[self.kind]} IF EXISTS {self.qualified}{cascade}"


@dataclass
class Plan:
    """Everything the run intends to do, so the dry run and the real run share one path."""

    schema: str | None
    current: list[DbObject] = field(default_factory=list)
    stale: list[DbObject] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    orphan_types: list[str] = field(default_factory=list)
    rebuild: bool = False
    reasons: list[str] = field(default_factory=list)
    has_version_table: bool = False
    revision: str | None = None
    head: str | None = None

    @property
    def drops(self) -> list[DbObject]:
        """Stale objects first, then the application's tables in foreign-key-safe order."""
        if not self.rebuild:
            return list(self.stale)
        order = {table.name: index for index, table in enumerate(Base.metadata.sorted_tables)}
        current = sorted(self.current, key=lambda obj: order.get(obj.name, 0), reverse=True)
        return [*self.stale, *current]

    @property
    def rows_at_risk(self) -> int:
        return sum(obj.rows or 0 for obj in self.drops if obj.kind == "TABLE")

    @property
    def is_noop(self) -> bool:
        return not self.drops and not self.rebuild


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qualify(schema: str | None, name: str) -> str:
    return f"{_quote(schema)}.{_quote(name)}" if schema else _quote(name)


def _section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 74 - len(title)))


def _row_line(obj: DbObject, label_width: int = 42) -> str:
    """One report line: name, kind when it is not a plain table, and its row count."""

    rows = "rows:   -" if obj.rows is None else f"rows: {obj.rows:,}"
    kind = "" if obj.kind == "TABLE" else f"  [{obj.kind}]"
    return f"  {f'{obj.name}{kind}':<{label_width}} {rows}"


def build_engine(settings: Settings) -> Engine:
    """Create a dedicated engine for DDL, resolving the URL exactly like Alembic does."""

    url = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL
    options: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


def resolve_schema(engine: Engine, requested: str | None) -> str | None:
    """The only schema this script may touch — ``public`` on PostgreSQL by default."""

    if requested:
        return requested
    if engine.dialect.name == "sqlite":
        return "main"
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COALESCE(current_schema(), 'public')")) or "public"


def _count_rows(connection: Connection, obj: DbObject) -> int | None:
    """Rows in a table, or ``None`` when it cannot be counted (views, permission gaps)."""

    if obj.kind != "TABLE":
        return None
    try:
        return int(connection.scalar(text(f"SELECT count(*) FROM {obj.qualified}")) or 0)
    except SQLAlchemyError:
        return None


def live_objects(engine: Engine, schema: str | None) -> list[DbObject]:
    """Every table and view in ``schema``, each carrying its row count."""

    inspector = inspect(engine)
    objects = [DbObject(name, "TABLE", schema) for name in sorted(inspector.get_table_names(schema=schema))]
    known = {obj.name for obj in objects}
    for name in sorted(inspector.get_view_names(schema=schema)):
        if name not in known:
            objects.append(DbObject(name, "VIEW", schema))
            known.add(name)

    with engine.connect() as connection:
        if engine.dialect.name == "postgresql" and schema:
            # Materialized views are invisible to the inspector yet still block table drops.
            try:
                rows = connection.execute(
                    text("SELECT matviewname FROM pg_matviews WHERE schemaname = :schema"),
                    {"schema": schema},
                ).fetchall()
            except SQLAlchemyError:
                rows = []
            for (name,) in rows:
                if name not in known:
                    objects.append(DbObject(str(name), "MATERIALIZED VIEW", schema))
        return [DbObject(obj.name, obj.kind, obj.schema, _count_rows(connection, obj)) for obj in objects]


def build_plan(
    engine: Engine,
    schema: str | None,
    *,
    keep: frozenset[str],
    mode: str,
    drop_orphan_types: bool,
) -> Plan:
    """Classify the live schema against ``Base.metadata`` and decide what has to change."""

    plan = Plan(schema=schema)
    present: set[str] = set()
    for obj in live_objects(engine, schema):
        present.add(obj.name)
        if obj.name in PROTECTED_TABLES:
            if obj.name == ALEMBIC_VERSION_TABLE:
                plan.has_version_table = True
            plan.protected.append(obj.name)
        elif obj.name in FOREIGN_TABLES or obj.name in keep:
            plan.protected.append(obj.name)
        elif obj.name in EXPECTED_TABLES:
            plan.current.append(obj)
        else:
            plan.stale.append(obj)
    plan.missing = sorted(EXPECTED_TABLES - present)

    plan.head = expected_head_revision()
    if plan.has_version_table:
        with engine.connect() as connection:
            plan.revision = connection.scalar(text(_alembic_revision_query(schema)))
    plan.rebuild, plan.reasons = _rebuild_decision(engine, plan, mode=mode)
    if drop_orphan_types and engine.dialect.name == "postgresql" and schema:
        plan.orphan_types = _types_left_orphaned(engine, schema, {obj.name for obj in plan.drops})
    return plan


def _alembic_revision_query(schema: str | None) -> str:
    return f"SELECT version_num FROM {_qualify(schema, ALEMBIC_VERSION_TABLE)} LIMIT 1"


def _rebuild_decision(engine: Engine, plan: Plan, *, mode: str) -> tuple[bool, list[str]]:
    """Decide whether the application's own tables have to be dropped and recreated.

    ``auto`` (the default) rebuilds only when the schema cannot be reconciled in place, so a
    second run never wipes data it has already cleaned. ``rebuild`` forces it, ``prune`` never.
    """

    if mode == "prune":
        return False, ["--prune-only: the application's tables are never dropped"]
    reasons: list[str] = []
    if plan.missing:
        shown = ", ".join(plan.missing[:8]) + (", …" if len(plan.missing) > 8 else "")
        reasons.append(f"{len(plan.missing)} expected table(s) do not exist: {shown}")
    if plan.head and plan.revision != plan.head:
        recorded = plan.revision or "(nothing)"
        reasons.append(f"alembic_version records {recorded}, but the code is at {plan.head}")
    reasons.extend(_column_drift_reasons(engine, plan))
    if mode == "rebuild":
        reasons.append("--rebuild was requested")
    return bool(reasons), reasons


def _column_drift_reasons(engine: Engine, plan: Plan) -> list[str]:
    """Columns the models declare that the live tables do not have.

    Absent columns are normally added by a pending migration, but a database whose
    ``alembic_version`` already matches head while its tables lag behind (hand-built or
    restored from a dump) can only converge by being recreated.
    """

    if not plan.current:
        return []
    inspector = inspect(engine)
    missing: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name, schema=plan.schema):
            continue
        live = {column["name"] for column in inspector.get_columns(table.name, schema=plan.schema)}
        missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in live)
    if not missing:
        return []
    shown = ", ".join(missing[:8]) + (", …" if len(missing) > 8 else "")
    return [f"{len(missing)} column(s) the models declare are absent: {shown}"]


def _types_left_orphaned(engine: Engine, schema: str | None, dropping: set[str]) -> list[str]:
    """Enum/domain types that *this run* leaves behind with no column referencing them.

    A legacy table's custom type is still in use while the table exists, so the orphan
    check has to be projected against the drop list instead of the pre-drop state —
    otherwise the cleanup would never notice the types it itself orphans.
    """

    if not dropping:
        return []
    query = text(
        "SELECT t.typname FROM pg_type t "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE n.nspname = :schema AND t.typtype IN ('e', 'd') "
        "AND EXISTS ("
        "  SELECT 1 FROM pg_attribute a "
        "  JOIN pg_class c ON c.oid = a.attrelid "
        "  JOIN pg_namespace cn ON cn.oid = c.relnamespace "
        "  WHERE a.atttypid = t.oid AND cn.nspname = :schema AND c.relname IN :dropping"
        ") "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM pg_attribute a "
        "  JOIN pg_class c ON c.oid = a.attrelid "
        "  JOIN pg_namespace cn ON cn.oid = c.relnamespace "
        "  WHERE a.atttypid = t.oid AND cn.nspname = :schema "
        "  AND c.relkind IN ('r', 'p') AND c.relname NOT IN :dropping"
        ") ORDER BY t.typname"
    ).bindparams(bindparam("dropping", expanding=True))
    try:
        with engine.connect() as connection:
            rows = connection.execute(query, {"schema": schema, "dropping": sorted(dropping)}).fetchall()
    except SQLAlchemyError:
        return []
    return [str(row[0]) for row in rows]


def _drop_version_statement(schema: str | None, dialect: Dialect) -> str:
    cascade = " CASCADE" if dialect.name == "postgresql" else ""
    return f"DROP TABLE IF EXISTS {_qualify(schema, ALEMBIC_VERSION_TABLE)}{cascade}"


def report(plan: Plan, dialect: Dialect, *, execute: bool, backup_dir: Path | None) -> None:
    """Print the classification, the impact, and the exact statements the run will issue."""

    _section("Target")
    print(f"  schema          : {plan.schema or '(connection default search path)'}")
    print(f"  expected tables : {len(EXPECTED_TABLES)} (from app/models)")
    print(f"  recorded revision: {plan.revision or '(none)'} / head in code: {plan.head or '(unknown)'}")
    status = "EXECUTE — the database will be changed" if execute else "DRY RUN — nothing is modified"
    print(f"  mode            : {status}")

    _section("Stale objects — not referenced by the code any more → drop")
    if plan.stale:
        print("\n".join(_row_line(obj) for obj in plan.stale))
    else:
        print("  none — the schema holds no orphan tables")

    if plan.rebuild:
        _section("Current tables — dropped and recreated from the migrations")
        print("\n".join(_row_line(obj) for obj in plan.current) or "  none present")
        _section("Why a rebuild is needed")
        for reason in plan.reasons:
            print(f"  - {reason}")
    else:
        _section("Current tables — left in place")
        print(f"  {len(plan.current)} table(s) match the migrations; their rows are kept")
        for reason in plan.reasons:
            print(f"  - {reason}")

    if plan.orphan_types:
        _section("PostgreSQL types orphaned by these drops → drop")
        print("  " + ", ".join(plan.orphan_types))

    if plan.protected:
        _section("Ignored")
        print("  " + ", ".join(sorted(set(plan.protected))))

    if plan.is_noop:
        _section("Nothing to do")
        print("  The schema already contains exactly the tables the code expects.")
        print("  Pass --rebuild to drop and recreate the application's tables anyway.")
        return

    _section("Impact")
    print(f"  objects to drop : {len(plan.drops)}{' (stale only)' if not plan.rebuild else ''}")
    print(f"  rows to lose    : {plan.rows_at_risk:,}")
    if backup_dir:
        print(f"  backup          : {backup_dir} (CSV + DDL written before the drops)")

    _section("Statements")
    for obj in plan.drops:
        print(f"  {obj.drop_statement(dialect)};")
    if plan.rebuild:
        if plan.has_version_table:
            print(f"  {_drop_version_statement(plan.schema, dialect)};")
        print("  python -m alembic upgrade head   # recreates the tables and stamps alembic_version")
    for type_name in plan.orphan_types:
        print(f"  DROP TYPE IF EXISTS {_qualify(plan.schema, type_name)} CASCADE;")


def export_backup(engine: Engine, objects: Sequence[DbObject], backup_dir: Path) -> list[Path]:
    """Write one CSV per table plus a DDL dump, so a cleaned database stays recoverable."""

    backup_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    ddl_path = backup_dir / "schema-before-cleanup.sql"
    with ddl_path.open("w", encoding="utf-8") as ddl_file:
        for obj in objects:
            if obj.kind != "TABLE":
                continue
            rows = _export_table(engine, obj, backup_dir)
            _export_ddl(engine, obj, ddl_file)
            written.append(backup_dir / f"{obj.name}.csv")
            print(f"  exported {obj.name} ({rows:,} rows) → {obj.name}.csv")
    written.append(ddl_path)
    return written


def _export_table(engine: Engine, obj: DbObject, backup_dir: Path) -> int:
    csv_path = backup_dir / f"{obj.name}.csv"
    rows = 0
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        with engine.connect() as connection:
            result = connection.execute(text(f"SELECT * FROM {obj.qualified}"))
            mappings = result.mappings()
            writer.writerow(list(mappings.keys()))
            for row in mappings:
                # Iterating a RowMapping yields its keys, so read the values explicitly.
                writer.writerow(["" if value is None else value for value in row.values()])
                rows += 1
    return rows


def _export_ddl(engine: Engine, obj: DbObject, ddl_file: Any) -> None:
    """Reflect the table and record its definition; a legacy table may not be reflectable."""

    ddl_file.write(f"-- {obj.kind} {obj.qualified}\n")
    try:
        table = Table(obj.name, MetaData(schema=obj.schema), autoload_with=engine)
        definition = str(CreateTable(table).compile(dialect=engine.dialect)).strip()
    except SQLAlchemyError as exc:
        definition = f"-- could not reflect {obj.name}: {str(exc).splitlines()[0]}"
    else:
        definition += ";"
    ddl_file.write(f"{definition}\n\n")


def execute_plan(engine: Engine, plan: Plan, *, backup_dir: Path | None, verbose: bool) -> None:
    """Issue the drops in one transaction, after an optional CSV/DDL backup."""

    if backup_dir:
        _section("Backup")
        files = export_backup(engine, plan.drops, backup_dir)
        print(f"  {len(files)} file(s) in {backup_dir}")

    _section("Dropping")
    with engine.begin() as connection:
        for obj in plan.drops:
            _run(connection, obj.drop_statement(engine.dialect), f"dropped {obj.kind.lower()} {obj.name}", verbose)
        if plan.rebuild and plan.has_version_table:
            _run(
                connection,
                _drop_version_statement(plan.schema, engine.dialect),
                f"dropped table {ALEMBIC_VERSION_TABLE}",
                verbose,
            )
    if plan.orphan_types:
        # Separate transaction: the types only become unreferenced once the tables are gone.
        with engine.begin() as connection:
            for type_name in plan.orphan_types:
                _run(
                    connection,
                    f"DROP TYPE IF EXISTS {_qualify(plan.schema, type_name)} CASCADE",
                    f"dropped type {type_name}",
                    verbose,
                )


def _run(connection: Connection, statement: str, message: str, verbose: bool) -> None:
    if verbose:
        print(f"  SQL  {statement}")
    connection.execute(text(statement))
    print(f"  {message}")


def alembic_config(url: str) -> Config:
    """Alembic configuration bound to the backend's own ini/scripts and the resolved URL.

    Mirrors ``app.db.schema.auto_upgrade_head``: ``alembic.ini`` ships a placeholder URL, so
    the real one has to be handed over explicitly, with ``%`` doubled for configparser.
    """

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPTS))
    config.set_main_option("sqlalchemy.url", escape_for_alembic(url))
    return config


def rebuild(engine: Engine, url: str, *, verbose: bool) -> None:
    """Recreate the current schema through the migration chain itself."""

    _section("Applying the migrations")
    command.upgrade(alembic_config(url), "head")
    if verbose:
        print("  SQL  alembic upgrade head")
    inspector = inspect(engine)
    for table in sorted(EXPECTED_TABLES):
        columns = inspector.get_columns(table) if inspector.has_table(table) else []
        suffix = f" ({len(columns)} columns)" if columns else "  \u2014 NOT CREATED"
        print(f"  {table}{suffix}")


def verify(engine: Engine, plan: Plan) -> int:
    """Confirm the cleaned schema matches the code; returns the process exit code."""

    _section("Verification")
    with Session(engine) as session:
        drift = detect_schema_drift(session)
        recorded = current_revision(session)
    present = set(inspect(engine).get_table_names())
    skip = EXPECTED_TABLES | FOREIGN_TABLES | PROTECTED_TABLES
    leftover = sorted(name for name in present if name not in skip)
    print(f"  tables found    : {len(present)} ({len(EXPECTED_TABLES)} expected)")
    print(f"  alembic revision: {recorded or '(none)'} / expected {plan.head or '(unknown)'}")
    if leftover:
        print(f"  still stale     : {', '.join(leftover)}")
    if drift is not None:
        print(f"  schema drift    : {drift.get('details') or drift.get('message')}")
        return 2
    if plan.head and recorded and recorded != plan.head:
        print("  schema drift    : alembic_version does not match the head revision in the code")
        if not plan.rebuild:
            print("                    re-run without --prune-only to rebuild from the migrations, or:")
            print("                    python -m alembic stamp head   # if the tables really are correct")
        return 2
    print("  drift check     : clean — every expected table and critical column exists")
    return 0


def _print_next_steps(plan: Plan) -> None:
    """What a database with no rows and no users still needs before anyone can sign in."""

    _section("Next steps")
    print("  1. Create a sign-in again (the users table is empty after a rebuild):")
    print(
        "       SEED_USER_EMAIL=you@example.com SEED_USER_PASSWORD=... "
        "python scripts/seed_user.py"
    )
    print("  2. Reload the master data / catalogues — from the app's import screens, or from the")
    if any(obj.kind == "TABLE" and (obj.rows or 0) for obj in plan.drops):
        print("       CSV export this run wrote (--backup-dir).")
    else:
        print("       spreadsheet exports kept outside the repository.")
    print("  3. Delete backend/scripts/temp_clean_database.py: it is a one-off maintenance helper.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="temp_clean_database.py",
        description="Drop stale tables and rebuild the schema from the migrations.",
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--rebuild",
        action="store_true",
        help="force a drop and recreate of the application's tables, even when they look current",
    )
    scope.add_argument(
        "--prune-only",
        action="store_true",
        help="drop stale tables only; keep the application's tables and their rows",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform the drops and the rebuild; without this flag only a report is printed",
    )
    parser.add_argument("--confirm", metavar="PHRASE", help=f"guard phrase required by --execute: {CONFIRM_PHRASE}")
    parser.add_argument("--schema", help="schema to clean (default: the connection's current schema)")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="TABLE",
        help="comma-separated names never to drop (repeatable)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        metavar="DIR",
        help="export every table that will be dropped to CSV + DDL in DIR before dropping it",
    )
    parser.add_argument(
        "--drop-orphan-types",
        action="store_true",
        help="PostgreSQL only: also drop enum/domain types that no column references any more",
    )
    parser.add_argument(
        "--allow-hosted",
        action="store_true",
        help=f"permit running against {', '.join(sorted(HOSTED_ENVIRONMENTS))}",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="print each statement as it runs")
    return parser.parse_args(argv)


def _redact(url: str) -> str:
    """Print the target database without revealing its credentials."""

    if "@" not in url:
        return url
    scheme, _, remainder = url.partition("://")
    _, _, host = remainder.rpartition("@")
    return f"{scheme}://***@{host}"


def main(argv: Sequence[str] | None = None) -> int:
    # Alembic logs to stderr while this report goes to stdout; line buffering keeps the two
    # interleaved correctly when the output is piped or redirected to a file.
    sys.stdout.reconfigure(line_buffering=True)

    args = parse_args(argv)
    settings = get_settings()
    url = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL

    print("Well-Costing — temporary database cleaner")
    print(f"  environment : {settings.ENVIRONMENT}")
    print(f"  database    : {_redact(url)}")

    if settings.ENVIRONMENT in HOSTED_ENVIRONMENTS and not args.allow_hosted:
        print(
            f"\nRefusing to run against a hosted environment ({settings.ENVIRONMENT}). "
            "Confirm the database really is disposable, then re-run with --allow-hosted.",
            file=sys.stderr,
        )
        return 1
    if not EXPECTED_TABLES:
        print("\nNo models are registered on Base.metadata; refusing to drop anything.", file=sys.stderr)
        return 1
    if args.execute and args.confirm != CONFIRM_PHRASE:
        print(
            f"\n--execute requires --confirm {CONFIRM_PHRASE}: every table listed loses its rows.",
            file=sys.stderr,
        )
        return 1

    mode = "rebuild" if args.rebuild else "prune" if args.prune_only else "auto"
    engine = build_engine(settings)
    try:
        schema = resolve_schema(engine, args.schema)
        keep = frozenset(name.strip() for item in args.keep for name in item.split(",") if name.strip())
        plan = build_plan(
            engine,
            schema,
            keep=keep,
            mode=mode,
            drop_orphan_types=args.drop_orphan_types,
        )
        report(plan, engine.dialect, execute=args.execute, backup_dir=args.backup_dir)
        if plan.is_noop:
            return 0
        if not args.execute:
            print("\nDry run complete — nothing was changed. Re-run with --execute to apply the plan.")
            return 0

        execute_plan(engine, plan, backup_dir=args.backup_dir, verbose=args.verbose)
        if plan.rebuild:
            rebuild(engine, url, verbose=args.verbose)
        code = verify(engine, plan)
        if code == 0 and plan.rebuild:
            _print_next_steps(plan)
        return code
    except SQLAlchemyError as exc:
        print(f"\nDatabase error: {str(exc).splitlines()[0]}", file=sys.stderr)
        print(
            "Check DATABASE_URL / MIGRATION_DATABASE_URL in backend/.env and that the role "
            "owns these tables — managed providers usually need their admin role for DDL.",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
