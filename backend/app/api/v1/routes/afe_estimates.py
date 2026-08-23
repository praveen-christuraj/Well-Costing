"""AFE Cost Estimate routes — well-scoped unit rates for AFE lines."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.afe_estimates import AfeCostEstimateRead, AfeCostEstimateSaveRequest
from app.services.afe_estimates import AfeEstimateService

router = APIRouter(prefix="/afes/{afe_id}/cost-estimate", tags=["AFE Cost Estimates"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=AfeCostEstimateRead)
def get_afe_cost_estimate(
    afe_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> AfeCostEstimateRead:
    """The AFE's lines joined with their saved well-scoped unit rates."""
    return AfeEstimateService(session, current_user.id).get_estimate(afe_id)


@router.put("/rates", response_model=AfeCostEstimateRead)
def save_afe_cost_estimate_rates(
    afe_id: UUID,
    payload: AfeCostEstimateSaveRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> AfeCostEstimateRead:
    """Save unit rates for AFE lines and return the refreshed estimate."""
    return AfeEstimateService(session, current_user.id).save_rates(afe_id, payload)


@router.get("/export")
def export_afe_cost_estimate(
    afe_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """Printable Excel record of the priced AFE, for filing and sign-off."""
    content = AfeEstimateService(session, current_user.id).export_workbook(afe_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="afe-cost-estimate.xlsx"'},
    )
