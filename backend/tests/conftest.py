"""Shared backend test fixtures."""

import os
from collections.abc import Generator

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("CORS_ORIGINS", '["http://testserver"]')

import pytest
from app.core.config import Settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

TEST_PASSWORD = "Correct-Horse-Battery-1!"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory relational database session."""

    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless asked, PostgreSQL (the deployment
    # target) always enforces them. Turn the pragma on so a DELETE that
    # orphans a child row fails here instead of only in production.
    @event.listens_for(test_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    with Session(test_engine, expire_on_commit=False) as session:
        yield session
        session.rollback()
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def seeded_user(db_session: Session) -> User:
    """Create an active test user with one minimal role."""

    role = Role(name="viewer", description="Phase 1 test role")
    user = User(
        email="engineer@example.com",
        full_name="Test Engineer",
        hashed_password=hash_password(TEST_PASSWORD),
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session: Session, seeded_user: User) -> Generator[TestClient, None, None]:
    """Provide a TestClient with its database dependency overridden."""

    del seeded_user
    settings = Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        CORS_ORIGINS=["http://testserver"],
    )
    application = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()
