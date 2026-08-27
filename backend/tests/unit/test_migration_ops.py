"""Placeholder codes for master-data backfills must fit short VARCHAR columns."""

from uuid import UUID

import sqlalchemy as sa
from app.db.migration_ops import string_column_max_length, unique_placeholder_code

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
