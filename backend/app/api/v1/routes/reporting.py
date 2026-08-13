"""Phase 9 shared-dimension reporting and Excel export routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.reporting import (
    CostOverviewReport,
    CostReportFilters,
    ReportingContractRead,
)
from app.services.reporting import ReportingService

router = APIRouter(prefix="/reports", tags=["reporting"])


@router.get("/contracts/v1", response_model=ReportingContractRead)
def reporting_contract_v1(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ReportingContractRead:
    del current_user, session
    return ReportingService.contract()


@router.get("/cost-overview", response_model=CostOverviewReport)
def cost_overview(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    filters: Annotated[CostReportFilters, Depends()],
) -> CostOverviewReport:
    return ReportingService(session, current_user).overview(filters)


@router.get("/cost-overview/export")
def export_cost_overview(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    filters: Annotated[CostReportFilters, Depends()],
) -> Response:
    return Response(
        content=ReportingService(session, current_user).export(filters),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="cost-overview.xlsx"'},
    )
