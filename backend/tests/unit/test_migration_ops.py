"""Placeholder codes for master-data backfills must fit short VARCHAR columns."""

from uuid import UUID

import sqlalchemy as sa
from app.db.migration_ops import (
    _suffixed,
    declared_primary_key_families,
    string_column_max_length,
    type_family,
    unique_placeholder_code,
)
from sqlalchemy.dialects import postgresql, sqlite

# The UUID that aborted Termux: C{uuid} is 37 characters, VARCHAR(10) rejects it.
TERMUX_CURRENCY_ID = UUID("fe8f4fe6-14dd-4eab-a8fb-a9ae2d367477")


def test_integer_id_keeps_short_readable_code() -> None:
    assert unique_placeholder_code(1, set(), 10, prefix="C") == "C1"
    assert unique_placeholder_code(5, set(), 50, prefix="TMP") == "TMP5"


def test_uuid_id_fits_varchar_10() -> None:
    code = unique_placeholder_code(TERMUX_CURRENCY_ID, set(), 10, prefix="C")
    assert 0 < len(code) <= 10
    assert code != f"C{TERMUX_CURRENCY_ID}"


def test_uuid_placeholders_are_unique_within_varchar_10() -> None:
    existing = {"USD", "EUR"}
    codes: set[str] = set()
    for index in range(200):
        code = unique_placeholder_code(UUID(int=index + 1), existing | codes, 10, prefix="C")
        assert 0 < len(code) <= 10
        assert code not in existing
        assert code not in codes
        codes.add(code)


def test_collision_with_naive_code_still_fits() -> None:
    code = unique_placeholder_code(1, {"C1"}, 10, prefix="C")
    assert code != "C1"
    assert 0 < len(code) <= 10


def test_string_column_max_length_reads_varchar() -> None:
    assert string_column_max_length(sa.String(10)) == 10
    assert string_column_max_length(sa.Text()) == 50


def test_type_family_ignores_length_and_precision() -> None:
    """A foreign key only needs both sides to share a base type."""

    pg = postgresql.dialect()
    assert type_family(sa.String(50), pg) == "VARCHAR"
    assert type_family(sa.Text(), pg) == "TEXT"
    assert type_family(sa.Numeric(18, 2), pg) == "NUMERIC"
    assert type_family(sa.Integer(), pg) == "INTEGER"
    assert type_family(sa.Uuid(), pg) == "UUID"
    # A reflected column type reports the same family as the declared one.
    assert type_family(postgresql.UUID(), pg) == type_family(sa.Uuid(), pg)
    assert type_family(postgresql.INTEGER(), pg) == type_family(sa.Integer(), pg)
    assert type_family(postgresql.VARCHAR(36), pg) == type_family(sa.String(36), pg)


def test_type_family_separates_uuid_from_integer_on_sqlite_too() -> None:
    """The mismatch has to be detectable on the SQLite used by the test suite."""

    sqlite_dialect = sqlite.dialect()
    assert type_family(sa.Uuid(), sqlite_dialect) == "CHAR"
    assert type_family(sa.String(36), sqlite_dialect) == "VARCHAR"
    assert type_family(sa.Integer(), sqlite_dialect) == "INTEGER"


def test_declared_primary_key_resolves_without_attaching_caller_columns() -> None:
    """Probing a definition must not consume the columns alembic still needs."""

    id_column = sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)
    columns = [
        id_column,
        sa.Column("chemical_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chemical_id"], ["mud_chemicals.id"], name="fk_rates"),
        sa.PrimaryKeyConstraint("id", name="pk_rates"),
    ]
    kwargs: dict[str, object] = {}

    pg = postgresql.dialect()
    assert declared_primary_key_families("mud_chemical_rates", columns, kwargs, pg) == ["INTEGER"]
    assert id_column.table is None, "the probe attached the caller's column"

    sqlite_dialect = sqlite.dialect()
    assert declared_primary_key_families("mud_chemical_rates", columns, kwargs, sqlite_dialect) == [
        "INTEGER"
    ]


def test_suffixed_name_fits_the_identifier_limit() -> None:
    """PostgreSQL truncates identifiers at 63 characters."""

    assert _suffixed("mud_chemicals", "pre_20260827_0005") == "mud_chemicals_pre_20260827_0005"
    long_name = _suffixed("a" * 80, "pre_20260827_0005")
    assert len(long_name) <= 63
    assert long_name.endswith("_pre_20260827_0005")
