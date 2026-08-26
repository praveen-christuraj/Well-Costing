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
    """Save the submitted AFE's current estimate rates and return it refreshed."""
    return AfeEstimateService(session, current_user.id).save_rates(afe_id, payload)


@router.post("/audit/print", status_code=204)
def audit_afe_cost_estimate_print(
    afe_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """Record a browser print of the current submitted AFE Cost Estimate."""
    AfeEstimateService(session, current_user.id).record_print(afe_id)
    return Response(status_code=204)


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
