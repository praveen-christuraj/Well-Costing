"""Database engine, session factory, and FastAPI session dependency."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def _create_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options.update(
            {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        )
    return create_engine(database_url, **options)


engine = _create_engine(get_settings().DATABASE_URL)

if engine.dialect.name == "sqlite":
    # Historical migrations declared `DEFAULT (now())`, which SQLite cannot
    # execute natively (its built-in is CURRENT_TIMESTAMP). Register the
    # function so databases built from those migrations insert fine.
    def _sqlite_now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    def _register_sqlite_helpers(dbapi_connection: Any, _connection_record: Any) -> None:
        # sqlite3.Connection#create_function is not exposed by SQLAlchemy's
        # DBAPIConnection protocol type.
        dbapi_connection.create_function("now", 0, _sqlite_now)  # type: ignore[attr-defined]

    event.listen(engine, "connect", _register_sqlite_helpers)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per request."""

    with SessionLocal() as session:
        yield session
