"""Configured database integration smoke test."""

import pytest
from app.db.session import engine
from sqlalchemy import text


@pytest.mark.integration
def test_configured_database_accepts_select_one() -> None:
    """Use PostgreSQL in CI and the configured SQLite fallback in isolated tests."""

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
