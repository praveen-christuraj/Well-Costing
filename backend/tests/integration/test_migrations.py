"""Migrations must survive databases that already contain some of the schema.

Deployments provisioned before the ``20260827_0001`` baseline (or by an older
build of the app) can hold tables such as ``currencies`` while
``alembic_version`` still points at an earlier revision. Before these tests the
upgrade aborted with ``DuplicateTable: relation "currencies" already exists``
and the deployment could not move forward.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20260827_0005"
EXPECTED_TABLES = {
    "users",
    "roles",
    "user_roles",
    "uom",
    "currencies",
    "phases",
    "activities",
    "hole_sections",
    "audit_logs",
    "vendor_suppliers",
    "purchase_orders_service_orders",
}


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}"


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _columns(url: str, table: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def _current_revision(url: str) -> str:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()


def test_upgrade_head_on_empty_database(database_url: str) -> None:
    """The happy path still creates the whole schema."""

    command.upgrade(_alembic_config(database_url), "head")

    assert _tables(database_url) >= EXPECTED_TABLES
    assert _current_revision(database_url) == HEAD_REVISION


def test_upgrade_replays_over_existing_tables(database_url: str) -> None:
    """Re-running a revision whose tables exist finishes instead of failing.

    Reproduces the reported Termux failure: the master-data tables are already
    present while ``alembic_version`` was left at the previous revision.
    """

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '20260827_0001'"))
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    assert _tables(database_url) >= EXPECTED_TABLES
    assert _current_revision(database_url) == HEAD_REVISION


def test_upgrade_completes_legacy_table_and_keeps_data(database_url: str) -> None:
    """A pre-existing table from an older schema gains the missing columns."""

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE currencies ("
                "id INTEGER PRIMARY KEY, "
                "currency_code VARCHAR(10) NOT NULL, "
                "currency_name VARCHAR(100) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO currencies (currency_code, currency_name) VALUES ('USD', 'Dollar')")
        )
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    columns = _columns(database_url, "currencies")
    assert columns >= {"currency_symbol", "is_deleted", "created_at", "updated_at", "created_by"}
    assert _current_revision(database_url) == HEAD_REVISION

    engine = create_engine(database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT currency_code, currency_symbol, created_at FROM currencies")
        ).one()
    engine.dispose()
    assert row.currency_code == "USD"
    # Columns added with a server default are backfilled for existing rows.
    assert row.created_at is not None
    # Required string columns added onto a legacy table are filled, not left NULL.
    assert row.currency_symbol == ""


def test_upgrade_backfills_null_currency_code_for_uuid_primary_keys(database_url: str) -> None:
    """Legacy currencies tables may use UUID ids; placeholders must fit VARCHAR(10).

    Reproduces the Termux failure:
    ``StringDataRightTruncation: value too long for type character varying(10)``
    when revision ``20260827_0004`` concatenated ``C`` with the full UUID.
    """

    row_id = "fe8f4fe6-14dd-4eab-a8fb-a9ae2d367477"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE currencies ("
                "id VARCHAR(36) PRIMARY KEY, "
                "currency_code VARCHAR(10), "
                "currency_name VARCHAR(100))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO currencies (id, currency_code, currency_name) "
                "VALUES (:id, NULL, NULL)"
            ),
            {"id": row_id},
        )
        connection.execute(
            text(
                "INSERT INTO currencies (id, currency_code, currency_name) "
                "VALUES (:id, 'USD', 'Dollar')"
            ),
            {"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
        )
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, currency_code, currency_name, currency_symbol FROM currencies")
        ).fetchall()
    engine.dispose()

    assert _current_revision(database_url) == HEAD_REVISION
    codes = [row.currency_code for row in rows]
    assert all(code not in (None, "") for code in codes)
    assert all(len(code) <= 10 for code in codes)
    assert "USD" in codes
    assert len(set(codes)) == len(codes)


def test_upgrade_adds_currency_code_onto_uuid_legacy_table(database_url: str) -> None:
    """A legacy currencies table missing currency_code still upgrades.

    ``20260827_0002`` adds the column as nullable and must backfill a unique
    placeholder that fits VARCHAR(10) rather than ``C{uuid}``.
    """

    row_id = "fe8f4fe6-14dd-4eab-a8fb-a9ae2d367477"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE currencies ("
                "id VARCHAR(36) PRIMARY KEY, "
                "currency_name VARCHAR(100))"
            )
        )
        connection.execute(
            text("INSERT INTO currencies (id, currency_name) VALUES (:id, 'Unknown')"),
            {"id": row_id},
        )
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT currency_code, currency_name FROM currencies")
        ).one()
    engine.dispose()

    assert _current_revision(database_url) == HEAD_REVISION
    assert row.currency_code not in (None, "")
    assert len(row.currency_code) <= 10
    assert row.currency_name == "Unknown"


def _column_type(url: str, table: str, column: str) -> str:
    engine = create_engine(url)
    try:
        for candidate in inspect(engine).get_columns(table):
            if candidate["name"] == column:
                return str(candidate["type"])
    finally:
        engine.dispose()
    raise AssertionError(f"{table}.{column} does not exist")


def _foreign_keys(url: str, table: str) -> list[dict]:
    engine = create_engine(url)
    try:
        return list(inspect(engine).get_foreign_keys(table))
    finally:
        engine.dispose()


def test_upgrade_replaces_legacy_uuid_catalogue_tables(database_url: str) -> None:
    """A legacy catalogue table keyed by UUID is renamed aside, not adopted.

    Reproduces the Termux failure where ``20260827_0005`` aborted with
    ``DatatypeMismatch: Key columns "chemical_id" of the referencing table and
    "id" of the referenced table are of incompatible types: integer and uuid``
    because the database already held a UUID-keyed ``mud_chemicals``. The old
    table cannot host the rate table's foreign key and the ORM cannot map it
    either, so it is renamed aside with its rows and rebuilt as declared.
    """

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE mud_chemicals ("
                "id VARCHAR(36) PRIMARY KEY, part_number VARCHAR(100))"
            )
        )
        connection.execute(
            text("INSERT INTO mud_chemicals (id, part_number) VALUES ('legacy-1', 'P-1')")
        )
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    assert _current_revision(database_url) == HEAD_REVISION
    assert "mud_chemicals_pre_20260827_0005" in _tables(database_url)
    assert _column_type(database_url, "mud_chemicals", "id") == "INTEGER"

    engine = create_engine(database_url)
    with engine.connect() as connection:
        kept = connection.execute(
            text("SELECT part_number FROM mud_chemicals_pre_20260827_0005")
        ).scalar_one()
    engine.dispose()

    # The legacy rows survive under the new name for a manual migration.
    assert kept == "P-1"
    # The rebuilt table is the one the rate history points at.
    assert any(
        foreign_key["referred_table"] == "mud_chemicals"
        for foreign_key in _foreign_keys(database_url, "mud_chemical_rates")
    )


def test_upgrade_skips_foreign_key_to_legacy_uuid_table(database_url: str) -> None:
    """An unusable foreign key is skipped instead of aborting the upgrade.

    ``vendor_suppliers`` belongs to an earlier revision, so it is left alone
    when its primary key does not match; the foreign keys pointing at it cannot
    be created and are dropped with a warning rather than failing the migration.
    """

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE vendor_suppliers ("
                "id VARCHAR(36) PRIMARY KEY, "
                "vendor_code VARCHAR(50), "
                "vendor_name VARCHAR(200), "
                "is_deleted BOOLEAN DEFAULT 0)"
            )
        )
    engine.dispose()

    command.upgrade(_alembic_config(database_url), "head")

    assert _current_revision(database_url) == HEAD_REVISION
    assert "vendor_suppliers_pre_20260827_0005" not in _tables(database_url)
    assert not [
        foreign_key
        for foreign_key in _foreign_keys(database_url, "services")
        if foreign_key["referred_table"] == "vendor_suppliers"
    ]


POSTGRES_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set TEST_DATABASE_URL to an empty PostgreSQL database to run",
)
def test_upgrade_over_legacy_uuid_tables_on_postgresql() -> None:
    """The reported failure needs PostgreSQL: only it rejects the mismatched key.

    SQLite accepts a foreign key between an INTEGER and a VARCHAR column, so
    the ``DatatypeMismatch`` this guards against can only be reproduced against
    a real PostgreSQL server. Point ``TEST_DATABASE_URL`` at an empty database
    (``postgresql+psycopg://user:pass@host/dbname``) to run it.
    """

    url = POSTGRES_URL
    assert url is not None
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS mud_chemical_rates CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS mud_chemicals CASCADE"))
        connection.execute(
            text(
                "CREATE TABLE mud_chemicals ("
                "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "part_number VARCHAR(100))"
            )
        )
        connection.execute(text("INSERT INTO mud_chemicals (part_number) VALUES ('P-1')"))
    engine.dispose()

    command.upgrade(_alembic_config(url), "head")

    assert _current_revision(url) == HEAD_REVISION
    assert "mud_chemicals_pre_20260827_0005" in _tables(url)
    assert _column_type(url, "mud_chemicals", "id") == "INTEGER"
    assert any(
        foreign_key["referred_table"] == "mud_chemicals"
        for foreign_key in _foreign_keys(url, "mud_chemical_rates")
    )
