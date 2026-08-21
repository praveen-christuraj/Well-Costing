"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Process-level liveness without a database dependency."""

    status: Literal["alive"]
    environment: str
    version: str


class HealthResponse(BaseModel):
    """Application and database connectivity status."""

    status: Literal["healthy", "degraded"]
    database: Literal["connected", "disconnected", "schema_outdated"]
    environment: str
    version: str
    # Filled in when the database is reachable: "current" when the schema
    # matches the application, "outdated" when migrations are pending, and
    # "unknown" when the schema could not be verified (e.g. no connection).
    schema_status: Literal["current", "outdated", "unknown"] = "unknown"
    schema_message: str | None = None
