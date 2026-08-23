"""Regression tests for percent characters in migration database URLs.

A URL whose password needs percent-encoding (a literal ``%`` written as
``%25``) used to crash Alembic with ``ValueError: invalid interpolation
syntax`` before any migration could run.
"""

import pytest
from alembic.config import Config
from app.db.alembic_url import escape_for_alembic

PCT_URL = "postgresql+psycopg://wellcosting:wellcosting%251234@127.0.0.1:5432/wellcosting"


def test_escape_doubles_percent_signs() -> None:
    assert escape_for_alembic(PCT_URL) == PCT_URL.replace("%", "%%")


def test_escaped_url_round_trips_through_alembic_config() -> None:
    config = Config()

    config.set_main_option("sqlalchemy.url", escape_for_alembic(PCT_URL))

    # configparser un-escapes %% on read, so Alembic sees the intended URL.
    assert config.get_main_option("sqlalchemy.url") == PCT_URL


def test_raw_url_is_rejected_by_configparser() -> None:
    # Documents why escape_for_alembic exists: configparser's BasicInterpolation
    # refuses a single % in a value.
    with pytest.raises(ValueError, match="interpolation"):
        Config().set_main_option("sqlalchemy.url", PCT_URL)
