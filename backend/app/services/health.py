"""Application health-check orchestration."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.schema import detect_schema_drift
from app.schemas.health import HealthResponse

logger = logging.getLogger("app")


class HealthService:
    """Build health status without leaking or propagating database failures."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> HealthResponse:
        """Execute a lightweight database probe and always return a response.

        The database may be reachable yet behind the application schema, in
        which case it is reported as ``schema_outdated`` with a remediation
        message instead of staying silent until every list endpoint 500s.
        """

        database: str = "connected"
        schema_status = "unknown"
        schema_message: str | None = None
        try:
            self._session.execute(text("SELECT 1"))
            try:
                drift = detect_schema_drift(self._session)
            except SQLAlchemyError:
                drift = None
            if drift is None:
                schema_status = "current"
            else:
                database = "schema_outdated"
                schema_status = "outdated"
                schema_message = str(drift["message"])
                logger.warning(
                    "Database schema is behind the application code",
                    extra={"schema_drift": drift},
                )
        except SQLAlchemyError as exc:
            database = "disconnected"
            self._session.rollback()
            logger.warning("Database health check failed", extra={"error_type": type(exc).__name__})

        return HealthResponse(
            status="healthy" if database == "connected" else "degraded",
            database=database,
            environment=self._settings.ENVIRONMENT,
            version=self._settings.APP_VERSION,
            schema_status=schema_status,
            schema_message=schema_message,
        )
