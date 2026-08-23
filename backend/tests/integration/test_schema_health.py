"""Schema drift detection, actionable errors, and dev auto-migration tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD

BACKEND_DIR = Path(__file__).resolve().parents[2]
AUTH_JSON = {"email": "engineer@example.com", "password": TEST_PASSWORD}


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


def test_missing_afe_tables_report_schema_outdated(
    lenient_client: TestClient, db_session: Session
) -> None:
    """List endpoints give an actionable 503, and /health reports the drift.

    Regression: a database left behind the application's migrations (or a
    table/column missing for any other reason) used to surface as a generic
    HTTP 500 "An unexpected error occurred" on /afes, /wells, /projects, and
    /estimates, with no hint of the cause. The API now explains exactly what
    to run, and the health check reports the schema as outdated.
    """
    auth = _login(lenient_client)
    db_session.execute(text("DROP TABLE afe_lines"))
    db_session.execute(text("DROP TABLE afes"))
    db_session.commit()

    response = lenient_client.get("/api/v1/afes?page=1&page_size=500", headers=auth)

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
    """A missing column on a planning table is detected the same way.

    A partially applied migration chain (tables present, columns absent)
    produces the same failure class, so it must produce the same diagnosis.
    """
    auth = _login(lenient_client)
    db_session.execute(text("DROP TABLE afes"))
    db_session.execute(text("CREATE TABLE afes (id CHAR(32) PRIMARY KEY, code VARCHAR(100))"))
    db_session.commit()

    response = lenient_client.get("/api/v1/afes?page=1&page_size=500", headers=auth)

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "database_schema_outdated"

    health = lenient_client.get("/api/v1/health")
    assert health.json()["database"] == "schema_outdated"


def test_development_startup_auto_applies_pending_migrations(tmp_path: Path) -> None:
    """Booting in development upgrades a database left behind by the code.

    Regression: pulling new code without running `alembic upgrade head` left
    the local database behind, and every planning endpoint then 500ed. In
    development/termux environments the backend now applies pending
    migrations itself before serving requests.
    """
    db_path = tmp_path / "dev.db"
    url = f"sqlite+pysqlite:///{db_path}"
    command.upgrade(_alembic_config(url), "20260820_0016")

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

    settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL=url,
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        CORS_ORIGINS=["http://localhost:3000"],
    )
    with _client_for(url, settings) as test_client:
        auth = _login(test_client)
        health = test_client.get("/api/v1/health")
        assert health.json()["database"] == "connected"
        assert health.json()["schema_status"] == "current"
        listing = test_client.get("/api/v1/afes?page=1&page_size=500", headers=auth)
        assert listing.status_code == 200, listing.text

    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == "20260823_0023"


def test_migrations_round_trip_on_sqlite(tmp_path: Path) -> None:
    """upgrade head -> downgrade base -> upgrade head succeeds on SQLite.

    Regression: the SQLite chain broke mid-way in several places (reserved
    word in the reporting views, constraint DDL on existing tables, the
    legacy_alter_table pragma leaking between migrations, and batch rebuilds
    of view-referenced tables). A local SQLite database must be able to
    migrate up, roll back to an empty schema, and migrate up again.
    """
    db_path = tmp_path / "roundtrip.db"
    url = f"sqlite+pysqlite:///{db_path}"
    command.upgrade(_alembic_config(url), "head")
    command.downgrade(_alembic_config(url), "base")
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == "20260823_0023"
