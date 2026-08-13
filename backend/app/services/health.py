"""Application health-check orchestration."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.health import HealthResponse

logger = logging.getLogger("app")


class HealthService:
    """Build health status without leaking or propagating database failures."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> HealthResponse:
        """Execute a lightweight database probe and always return a response."""

        database: str = "connected"
        try:
            self._session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            database = "disconnected"
            self._session.rollback()
            logger.warning("Database health check failed", extra={"error_type": type(exc).__name__})

        return HealthResponse(
            status="healthy" if database == "connected" else "degraded",
            database=database,
            environment=self._settings.ENVIRONMENT,
            version=self._settings.APP_VERSION,
        )
