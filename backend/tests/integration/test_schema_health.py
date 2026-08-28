"""Schema drift detection, actionable errors, and dev auto-migration tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import detect_schema_drift
from app.db.session import get_db
from app.main import create_app
from app.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD

BACKEND_DIR = Path(__file__).resolve().parents[2]
AUTH_JSON = {"email": "engineer@example.com", "password": TEST_PASSWORD}
BASELINE_REVISION = "20260827_0007"


@pytest.fixture
def lenient_client(db_session: Session, seeded_user: User) -> Generator[TestClient, None, None]:
    """A client that returns the API's 5xx responses instead of raising.

    The drift tests assert on the 503 the API must return in production;
    the default client fixture re-raises server exceptions for debugging.
    """
    del seeded_user
    application = create_app(
        Settings(
            ENVIRONMENT="test",
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
            CORS_ORIGINS=["http://testserver"],
        )
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _client_for(url: str, settings: Settings) -> TestClient:
    application = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with Session(engine, expire_on_commit=False) as session:
            yield session
        engine.dispose()

    application.dependency_overrides[get_db] = override_get_db
    return TestClient(application, raise_server_exceptions=False)


def _login(client: TestClient) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json=AUTH_JSON)
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_dropped_auth_tables_report_schema_outdated(
    lenient_client: TestClient, db_session: Session
) -> None:
    """Endpoints give an actionable 503, and /health reports the drift.

    A database left behind the application's migrations (or a table missing
    for any other reason) must not surface as a generic HTTP 500 "An
    unexpected error occurred" with no hint of the cause. The API explains
    exactly what to run, and the health check reports the schema as outdated.
    """
    auth = _login(lenient_client)
    db_session.execute(text("DROP TABLE user_roles"))
    db_session.execute(text("DROP TABLE roles"))
    db_session.commit()
    # Clear the identity map so the next request has to hit the database;
    # without this, session.get() would serve the user it cached during login.
    db_session.expunge_all()

    # Resolving the bearer token loads the user together with its roles, so
    # the missing tables break the very first authenticated request.
    response = lenient_client.get("/api/v1/auth/me", headers=auth)

    assert response.status_code == 503, response.text
    error = response.json()["error"]
    assert error["code"] == "database_schema_outdated"
    assert "alembic upgrade head" in error["message"]

    health = lenient_client.get("/api/v1/health")
    assert health.status_code == 200
    body = health.json()
    assert body["database"] == "schema_outdated"
    assert body["schema_status"] == "outdated"
    assert body["schema_message"] and "alembic upgrade head" in body["schema_message"]

    readiness = lenient_client.get("/api/v1/ready")
    assert readiness.status_code == 503


def test_missing_columns_report_schema_outdated(
    lenient_client: TestClient, db_session: Session
) -> None:
    """A missing column on the users table is detected the same way.

    A partially applied migration chain (table present, columns absent)
    produces the same failure class, so it must produce the same diagnosis.
    """
    db_session.execute(text("DROP TABLE user_roles"))
    db_session.execute(text("DROP TABLE users"))
    db_session.execute(text("CREATE TABLE users (id CHAR(32) PRIMARY KEY, email VARCHAR(320))"))
    db_session.commit()

    # The health payload carries the remediation message; the specific
    # tables/columns are reported by the drift detector itself.
    drift = detect_schema_drift(db_session)
    assert drift is not None
    assert drift["missing_tables"] == ["user_roles"]
    assert "users.hashed_password" in drift["missing_columns"]
    assert "users.auth_provider" in drift["missing_columns"]

    health = lenient_client.get("/api/v1/health")

    assert health.status_code == 200
    body = health.json()
    assert body["database"] == "schema_outdated"
    assert body["schema_status"] == "outdated"
    assert "alembic upgrade head" in str(body["schema_message"])


def test_development_startup_applies_migrations_to_an_empty_database(tmp_path: Path) -> None:
    """Booting in development builds the schema a fresh database is missing.

    Regression: pulling new code without running `alembic upgrade head` left
    the local database behind, and every endpoint then 500ed. In
    development/termux environments the backend now applies pending
    migrations itself before serving requests.
    """
    db_path = tmp_path / "dev.db"
    url = f"sqlite+pysqlite:///{db_path}"

    settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL=url,
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        CORS_ORIGINS=["http://localhost:3000"],
    )

    # The lifespan hook runs the auto-migration; a user created afterwards
    # proves the tables exist and the app can serve against them.
    with _client_for(url, settings) as test_client:
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with Session(engine, expire_on_commit=False) as session:
            session.add(
                User(
                    email="engineer@example.com",
                    full_name="Test Engineer",
                    hashed_password=hash_password(TEST_PASSWORD),
                    roles=[Role(name="viewer", description="test")],
                )
            )
            session.commit()
        engine.dispose()

        auth = _login(test_client)
        health = test_client.get("/api/v1/health")
        assert health.json()["database"] == "connected"
        assert health.json()["schema_status"] == "current"
        profile = test_client.get("/api/v1/auth/me", headers=auth)
        assert profile.status_code == 200, profile.text
        assert profile.json()["email"] == "engineer@example.com"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == BASELINE_REVISION


def test_migrations_round_trip_on_sqlite(tmp_path: Path) -> None:
    """upgrade head -> downgrade base -> upgrade head succeeds on SQLite.

    A local SQLite database must be able to migrate up, roll back to an empty
    schema, and migrate up again — otherwise local development cannot reset.
    """
    db_path = tmp_path / "roundtrip.db"
    url = f"sqlite+pysqlite:///{db_path}"
    command.upgrade(_alembic_config(url), "head")
    command.downgrade(_alembic_config(url), "base")
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        tables = set(
            connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).scalars()
        )
    engine.dispose()

    assert version == BASELINE_REVISION
    assert {
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
        "rigs",
        "wells",
        "well_sections",
        "well_phases",
        "alembic_version",
    } <= tables
