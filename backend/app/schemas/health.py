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
    database: Literal["connected", "disconnected"]
    environment: str
    version: str
