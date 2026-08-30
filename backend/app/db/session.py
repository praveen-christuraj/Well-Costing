"""Database engine, session factory, and FastAPI session dependency."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import get_settings

#: How long a SQLite connection waits for a competing writer before failing.
SQLITE_BUSY_TIMEOUT_SECONDS = 30


def _is_memory_sqlite(database_url: str) -> bool:
    return ":memory:" in database_url or database_url.endswith("//")


def _create_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options.update(
            {
                # Wait for a competing writer instead of failing instantly.
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": SQLITE_BUSY_TIMEOUT_SECONDS,
                },
            }
        )
        if _is_memory_sqlite(database_url):
            # An in-memory database only exists on the connection that made it,
            # so every checkout must share that one connection.
            options["poolclass"] = StaticPool
        else:
            # A file-backed database must give every checkout its OWN
            # connection. Sharing one sqlite3 connection across request threads
            # (StaticPool) deadlocks the sync endpoint threadpool under
            # concurrent requests — every later request then hangs until the
            # process is restarted, which the frontend reports as 502s.
            options["poolclass"] = NullPool
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
        cursor = dbapi_connection.cursor()
        try:
            # WAL lets readers proceed while a writer holds the lock, and
            # busy_timeout makes writers queue politely instead of erroring.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_SECONDS * 1000}")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    event.listen(engine, "connect", _register_sqlite_helpers)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per request."""

    with SessionLocal() as session:
        yield session
