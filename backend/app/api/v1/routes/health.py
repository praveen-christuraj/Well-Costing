"""Liveness, compatibility health, and database readiness routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, LivenessResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/live", response_model=LivenessResponse)
def live(settings: Annotated[Settings, Depends(get_settings)]) -> LivenessResponse:
    """Report process liveness without opening a database connection."""

    return LivenessResponse(
        status="alive",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )


@router.get("/health", response_model=HealthResponse)
def health(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return compatibility health; database failures are represented as degraded."""

    return HealthService(session, settings).check()


@router.get("/ready", response_model=HealthResponse)
def ready(
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return HTTP 503 until the API can reach its database."""

    result = HealthService(session, settings).check()
    if result.status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
