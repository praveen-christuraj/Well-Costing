"""Phase 5 calculation trigger and results routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.calculations import EstimateCalculationResults
from app.services.calculations import EstimateCalculationService

router = APIRouter(prefix="/estimates", tags=["costing engine"])


@router.post("/{estimate_id}/calculate", response_model=EstimateCalculationResults)
def calculate_estimate(
    estimate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    version_id: Annotated[UUID | None, Query()] = None,
) -> EstimateCalculationResults:
    return EstimateCalculationService(session, current_user.id).calculate(estimate_id, version_id)


@router.get("/{estimate_id}/results", response_model=EstimateCalculationResults)
def get_results(
    estimate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    version_id: Annotated[UUID | None, Query()] = None,
) -> EstimateCalculationResults:
    return EstimateCalculationService(session, current_user.id).results(estimate_id, version_id)
