"""Health service degradation behavior."""

from unittest.mock import Mock

from app.core.config import Settings
from app.services.health import HealthService
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_database_failure_returns_degraded_instead_of_raising() -> None:
    session = Mock(spec=Session)
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("offline"))
    settings = Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
    )

    result = HealthService(session, settings).check()

    assert result.status == "degraded"
    assert result.database == "disconnected"
    session.rollback.assert_called_once()
