"""Health API tests."""

from collections.abc import Generator
from unittest.mock import Mock

from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_liveness_does_not_require_database_probe(client: TestClient) -> None:
    response = client.get("/api/v1/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "environment": "test",
        "version": "0.1.0",
    }


def test_health_reports_connected_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
        "environment": "test",
        "version": "0.1.0",
    }


def test_readiness_reports_connected_database(client: TestClient) -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    failing_session = Mock(spec=Session)
    failing_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("offline"))
    settings = Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
    )
    application = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        yield failing_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        response = test_client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    failing_session.rollback.assert_called_once()
